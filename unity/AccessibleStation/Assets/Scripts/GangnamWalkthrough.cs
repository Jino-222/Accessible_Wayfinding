using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.Simulation;

[Serializable] public class WalkStart {public string label;public bool closed;}
[Serializable] public class WalkClosure {public bool closed;}
[Serializable] public class WalkReply {
    public string session,prediction_file,state,reason,localization_reason;
    public int frame,inliers,recovery_count;public float time_s,elapsed_ms,reprojection_px,remaining_m;
    public bool success,accepted,arrow_visible;public float[] position,pose,target;
}
[Serializable] public class WalkObservation {
    public int frame;public float time_s,http_ms;public string condition,input_image,transport_error;
    public float[] reference_pose;public bool visible,blackout;public WalkReply prediction;
}
[Serializable] public class WalkVideoFrame {
    public int frame,observation_frame;public float time_s;public string image,state;public bool visible,blackout;
}
[Serializable] public class WalkRun {
    public string condition,final_state,prediction_file,unity_version,movement;
    public int video_frames,observations;public float fps,duration_s;public bool xr_tracking;
}

public class GangnamWalkthrough:MonoBehaviour {
    public Camera arCamera;public ARSession session;
    SimulationCameraPoseProvider provider;WalkSpec spec;WalkReply reply;
    string sid,folder,label,error="",predictionFile="";bool busy,manual,loss,closed,transportLost;
    int tick,observations;float clock,lastReply=-100;const float Height=1.2f,Fps=15f;
    LineRenderer line;GameObject arrow;RenderTexture queryRt,viewRt;Font font;
    const string Server="http://127.0.0.1:8768";
    string Output=>Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"AccessibleWayfinding/research/gangnam-walk");
    void Awake(){
        spec=JsonUtility.FromJson<WalkSpec>(File.ReadAllText(Path.Combine(Application.streamingAssetsPath,"gangnam-walk.json")));
        Application.runInBackground=true;QualitySettings.vSyncCount=0;
        font=Font.CreateDynamicFontFromOSFont("Malgun Gothic",20);
        var mat=new Material(Shader.Find("Unlit/Color"));mat.color=new Color(.12f,.91f,.65f);
        line=new GameObject("Estimated approach path").AddComponent<LineRenderer>();line.material=mat;line.positionCount=2;
        line.startWidth=.07f;line.endWidth=.07f;line.enabled=false;
        arrow=new GameObject("Estimated direction");arrow.AddComponent<MeshRenderer>().material=mat;
        var mesh=new Mesh{vertices=new[]{new Vector3(0,0,.55f),new Vector3(-.3f,0,0),new Vector3(-.10f,0,0),new Vector3(-.10f,0,-.5f),new Vector3(.10f,0,-.5f),new Vector3(.10f,0,0),new Vector3(.3f,0,0)},triangles=new[]{0,6,1,2,4,3,2,5,4}};
        mesh.RecalculateNormals();arrow.AddComponent<MeshFilter>().mesh=mesh;arrow.SetActive(false);
        queryRt=new RenderTexture(640,360,24,RenderTextureFormat.ARGB32);viewRt=new RenderTexture(960,540,24,RenderTextureFormat.ARGB32);
    }
    IEnumerator Start(){
        float until=Time.realtimeSinceStartup+90;
        while(ARSession.state!=ARSessionState.SessionTracking&&Time.realtimeSinceStartup<until)yield return null;
        provider=FindAnyObjectByType<SimulationCameraPoseProvider>();for(int i=0;i<20;i++)yield return null;
        if(provider==null){Fail("XR Simulation provider unavailable");yield break;}
        if(Application.isBatchMode)yield return Guard(RunAll());
    }
    IEnumerator Guard(IEnumerator it){
        var stack=new Stack<IEnumerator>();stack.Push(it);
        while(stack.Count>0){object value=null;bool more=false;
            try{more=stack.Peek().MoveNext();if(more)value=stack.Peek().Current;}
            catch(Exception e){Fail(e.ToString());yield break;}
            if(!more){stack.Pop();continue;}if(value is IEnumerator nested)stack.Push(nested);else yield return value;
        }
    }
    void Finish(int code){
#if UNITY_EDITOR
        if(Application.isBatchMode){UnityEditor.SessionState.SetInt("AccessibleXR.ExitCode",code);UnityEditor.SessionState.SetBool("AccessibleXR.Finished",true);UnityEditor.EditorApplication.isPlaying=false;}
#endif
    }
    void Fail(string message){error=message;Hide();busy=false;manual=false;Debug.LogError("WALK_FAILED "+message);Finish(1);}
    void Hide(){line.enabled=false;arrow.SetActive(false);}
    void Update(){if(Time.realtimeSinceStartup-lastReply>1.5f||!session.enabled||ARSession.state!=ARSessionState.SessionTracking)Hide();}
    IEnumerator Post(string path,object body,bool read=true,bool fatal=false){
        using(var req=new UnityWebRequest(Server+path,"POST")){
            req.uploadHandler=new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(body)));req.downloadHandler=new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type","application/json");req.timeout=30;
            yield return req.SendWebRequest();
            if(req.result!=UnityWebRequest.Result.Success){error="HTTP "+req.responseCode+" "+req.error;Hide();if(fatal)throw new Exception(error);yield break;}
            if(read){reply=JsonUtility.FromJson<WalkReply>(req.downloadHandler.text);lastReply=Time.realtimeSinceStartup;}error="";
        }
    }
    static Matrix4x4 W()=>Matrix4x4.Scale(new Vector3(1,1,-1));
    static Matrix4x4 C()=>Matrix4x4.Scale(new Vector3(1,-1,1));
    static float[] Flat(Matrix4x4 m){var a=new float[16];for(int r=0;r<4;r++)for(int c=0;c<4;c++)a[r*4+c]=m[r,c];return a;}
    static Matrix4x4 Mat(float[] a){var m=Matrix4x4.identity;for(int r=0;r<4;r++)for(int c=0;c<4;c++)m[r,c]=a[r*4+c];return m;}
    static Vector3 U(float[] p)=>new Vector3(p[0],p[1],-p[2]);
    Vector3 PathAt(float distance){
        for(int i=1;i<spec.path.Length;i++){
            var a=U(spec.path[i-1].position);var b=U(spec.path[i].position);float length=Vector3.Distance(a,b);
            if(distance<=length)return Vector3.Lerp(a,b,distance/length);distance-=length;
        }return U(spec.path[spec.path.Length-1].position);
    }
    IEnumerator Move(float distance){
        var p=PathAt(distance)+Vector3.up*Height;var forward=PathAt(Mathf.Min(distance+.3f,spec.length))-PathAt(Mathf.Max(distance-.1f,0));
        if(forward.sqrMagnitude<.001f)forward=Vector3.back;
        provider.transform.SetPositionAndRotation(p,Quaternion.LookRotation(forward)*Quaternion.Euler(6,0,0));
        for(int i=0;i<2;i++)yield return null;
    }
    Texture2D Capture(bool query,bool blackout=false){
        var rt=query?queryRt:viewRt;var old=arCamera.targetTexture;var active=RenderTexture.active;
        arCamera.aspect=16f/9f;arCamera.targetTexture=rt;arCamera.Render();RenderTexture.active=rt;
        var im=new Texture2D(rt.width,rt.height,TextureFormat.RGB24,false);im.ReadPixels(new Rect(0,0,rt.width,rt.height),0,0);
        if(blackout){var px=new Color[rt.width*rt.height];for(int i=0;i<px.Length;i++)px[i]=new Color(.025f,.035f,.04f);im.SetPixels(px);}
        im.Apply();arCamera.targetTexture=old;RenderTexture.active=active;return im;
    }
    void Paint(){
        if(reply==null||!reply.arrow_visible||reply.pose==null||reply.pose.Length!=16||error!=""||!session.enabled||ARSession.state!=ARSessionState.SessionTracking){Hide();return;}
        // The device-local pose only maps the independently estimated image pose into render space.
        var mapToXR=arCamera.transform.localToWorldMatrix*(W()*Mat(reply.pose)*C()).inverse;
        var p=U(reply.position);p.y-=Height-.06f;var target=U(reply.target);target.y=p.y;var delta=target-p;
        line.enabled=true;line.SetPosition(0,mapToXR.MultiplyPoint3x4(p));line.SetPosition(1,mapToXR.MultiplyPoint3x4(p+Vector3.ClampMagnitude(delta,2.7f)));
        arrow.SetActive(true);arrow.transform.position=mapToXR.MultiplyPoint3x4(p+Vector3.ClampMagnitude(delta,1.9f));
        if(delta.sqrMagnitude>.001f)arrow.transform.rotation=mapToXR.rotation*Quaternion.LookRotation(delta);
    }
    IEnumerator Observe(bool blackout){
        Hide();var im=Capture(true,blackout);var png=im.EncodeToPNG();Destroy(im);
        string filename="input-"+tick.ToString("D5")+".png";File.WriteAllBytes(Path.Combine(folder,filename),png);
        var proj=arCamera.projectionMatrix;
        var body=new VInput{frame=tick,width=640,height=360,time_s=clock,image=Convert.ToBase64String(png),action="observe",camera_height=Height,resuming=transportLost,
            fx=proj[0,0]*320,fy=proj[1,1]*180,cx=(1-proj[0,2])*320-.5f,cy=(1+proj[1,2])*180-.5f};
        var truth=Flat(W()*arCamera.transform.localToWorldMatrix*C());float started=Time.realtimeSinceStartup;
        if(session.enabled&&ARSession.state==ARSessionState.SessionTracking)yield return Post("/sessions/"+sid+"/frame",body);
        else error="XR tracking unavailable";
        transportLost=error!="";if(!transportLost&&reply.frame==tick)Paint();else Hide();
        var row=new WalkObservation{frame=tick,time_s=clock,http_ms=(Time.realtimeSinceStartup-started)*1000,condition=label,input_image=filename,
            transport_error=error,reference_pose=truth,visible=line.enabled,blackout=blackout,prediction=transportLost?null:reply};
        File.AppendAllText(Path.Combine(folder,"observations.jsonl"),JsonUtility.ToJson(row)+"\n");observations++;
    }
    void VideoFrame(bool blackout){
        string file="view-"+tick.ToString("D5")+".jpg";var im=Capture(false,blackout);File.WriteAllBytes(Path.Combine(folder,file),im.EncodeToJPG(88));Destroy(im);
        var row=new WalkVideoFrame{frame=tick,time_s=clock,observation_frame=reply==null?-1:reply.frame,image=file,state=closed?"blocked":blackout||error!=""?"position_uncertain":reply?.state,visible=line.enabled,blackout=blackout};
        File.AppendAllText(Path.Combine(folder,"video.jsonl"),JsonUtility.ToJson(row)+"\n");
    }
    IEnumerator Begin(string name){
        label=name;tick=0;observations=0;clock=0;closed=false;loss=false;transportLost=false;reply=null;Hide();
        string run=Environment.GetEnvironmentVariable("WAYFINDING_WALK_RUN")??"development-v1";
        folder=Path.Combine(Output,"runs",run,name);
        if(Directory.Exists(folder)&&File.Exists(Path.Combine(folder,"observations.jsonl")))throw new Exception("Run already exists; select a new WAYFINDING_WALK_RUN");
        Directory.CreateDirectory(folder);yield return Post("/sessions",new WalkStart{label=name},true,true);sid=reply.session;predictionFile=reply.prediction_file;
        yield return Move(0);
    }
    IEnumerator RunAll(){
        busy=true;string cases=Environment.GetEnvironmentVariable("WAYFINDING_WALK_CASES")??"normal,loss,closed";
        foreach(string condition in cases.Split(',')){
            yield return Begin(condition);float distance=0,arrivedAt=-1;
            for(tick=0;tick<900;tick++){
                clock=tick/Fps;bool blackout=condition=="loss"&&clock>=12&&clock<15;
                if(condition=="closed"&&clock>=7&&!closed){closed=true;Hide();yield return Post("/sessions/"+sid+"/closure",new WalkClosure{closed=true},false,true);}
                if(tick%8==0)yield return Observe(blackout);
                if(blackout||closed)Hide();
                VideoFrame(blackout);
                if(reply!=null&&reply.state=="arrived"&&arrivedAt<0)arrivedAt=clock;
                if((arrivedAt>=0&&clock-arrivedAt>=2)||(condition=="closed"&&clock>=15))break;
                // Scripted user movement is separate from the image-driven guidance experiment.
                if(!blackout&&!closed&&reply!=null&&reply.state=="guiding")distance=Mathf.Min(distance+.65f/Fps,spec.length);
                yield return Move(distance);
                if(tick%150==0)Debug.Log("WALK_PROGRESS "+condition+" "+tick+" "+reply?.state+" "+distance);
            }
            var run=new WalkRun{condition=condition,final_state=reply?.state,prediction_file=predictionFile,unity_version=Application.unityVersion,
                movement="scripted user along registered path; image-only guidance; video sampled at 15 fps, not real-time inference benchmark",video_frames=Mathf.Min(tick+1,900),observations=observations,fps=Fps,duration_s=Mathf.Min(tick+1,900)/Fps,xr_tracking=ARSession.state==ARSessionState.SessionTracking};
            File.WriteAllText(Path.Combine(folder,"run.json"),JsonUtility.ToJson(run,true));
            using(var request=UnityWebRequest.Delete(Server+"/sessions/"+sid))yield return request.SendWebRequest();
            Debug.Log("WALK_SCENARIO_COMPLETE "+condition+" "+run.final_state);
        }busy=false;Hide();Finish(0);
    }
    IEnumerator Manual(){
        busy=true;manual=true;yield return Begin("manual-"+Guid.NewGuid().ToString("N").Substring(0,8));float start=Time.realtimeSinceStartup;
        while(manual){clock=Time.realtimeSinceStartup-start;yield return Observe(loss);VideoFrame(loss);tick++;yield return new WaitForSecondsRealtime(.25f);}
        Hide();busy=false;
    }
    IEnumerator SetClosed(){Hide();yield return Post("/sessions/"+sid+"/closure",new WalkClosure{closed=closed},false);}
    void OnGUI(){
        if(Application.isBatchMode)return;
        GUI.skin.font=font;GUI.skin.label.fontSize=17;GUI.skin.button.fontSize=17;
        GUILayout.BeginArea(new Rect(20,20,350,380),GUI.skin.box);
        GUILayout.Label("강남역 접근 구간 · 가상 재현");GUILayout.Label("목적지  /  B2 엘리베이터 앞");
        GUILayout.Label((reply?.state??"준비")+"  "+error);
        if(reply!=null&&reply.state=="guiding")GUILayout.Label("추정 남은 거리  "+reply.remaining_m.ToString("F1")+" m");
        if(!busy&&provider!=null&&GUILayout.Button("직접 이동 시작"))StartCoroutine(Guard(Manual()));
        if(!busy&&provider!=null&&GUILayout.Button("3개 시나리오 자동 실행"))StartCoroutine(Guard(RunAll()));
        if(manual){
            GUILayout.Label("마우스 오른쪽 + WASD로 이동·회전");
            if(GUILayout.Button("앞으로 0.5 m")){var f=provider.transform.forward;f.y=0;provider.transform.position+=f.normalized*.5f;}
            if(GUILayout.Button("오른쪽으로 15°"))provider.transform.Rotate(Vector3.up,15,Space.World);
            if(GUILayout.Button(loss?"영상 복구":"영상 가림 시험")){loss=!loss;if(loss)Hide();}
            if(GUILayout.Button(closed?"접근 재개":"엘리베이터 접근 중단")){closed=!closed;StartCoroutine(Guard(SetClosed()));}
            if(GUILayout.Button("종료"))manual=false;
        }
        GUILayout.Label("현장 경로 안내용이 아닌 연구 데모");GUILayout.EndArea();
    }
}
