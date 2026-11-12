using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.Simulation;
using Unity.XR.CoreUtils;

[Serializable] public class VStart {public string label;}
[Serializable] public class VInput {
    public int frame,width=640,height=400;public float time_s,fx,fy,cx,cy,camera_height;public string image,action;public bool resuming;
}
[Serializable] public class VReply {
    public string session,prediction_file,state,reason,floor,current_node,localization_reason;
    public int frame,inliers,recovery_count;public float elapsed_ms,reprojection_px;
    public bool success,accepted,arrow_visible,action_applied;public float[] position,pose,target;public XRWaypoint[] waypoints;
}
[Serializable] public class VFault {public float delay_s;public int status=200;}
[Serializable] public class VRecord {
    public int frame;public float time_s,http_ms,camera_height;public string condition,action,input_image,view_image,transport_error;
    public float[] reference_pose,local_xr_pose,map_to_xr;public bool visible,expired_during_wait,origin_reset;public VReply prediction;
}
[Serializable] public class VRun {public string condition,final_state,prediction_file;public int frames;public bool arrived;}
[Serializable] public class VBatch {public bool executed;public string unity_version,method;public VRun[] runs;}

public class VisualWalkthrough:MonoBehaviour {
    public Camera arCamera;public ARSession session;
    SimulationCameraPoseProvider provider;XROrigin origin;VReply reply;string sid,label,folder,error="";
    int frame;float clock,lastReply=-100;float height=1.2f;bool busy,manual,expired,transportLost;string manualAction="observe";
    LineRenderer line;GameObject arrow;RenderTexture rt;Matrix4x4 mapToXR=Matrix4x4.identity;
    Quaternion viewRotation=Quaternion.Euler(12,180,0);
    const string Server="http://127.0.0.1:8766";
    string Output=>Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"AccessibleWayfinding/research/visual-runtime");
    void Awake(){
        Application.runInBackground=true;QualitySettings.vSyncCount=0;
        var mat=new Material(Shader.Find("Unlit/Color"));mat.color=new Color(.04f,.9f,.68f);
        line=new GameObject("Image estimated route").AddComponent<LineRenderer>();line.material=mat;line.positionCount=2;line.startWidth=.1f;line.endWidth=.1f;line.enabled=false;
        arrow=new GameObject("Image estimated arrow");arrow.AddComponent<MeshRenderer>().material=mat;
        var mesh=new Mesh{vertices=new[]{new Vector3(0,0,.7f),new Vector3(-.32f,0,0),new Vector3(-.10f,0,0),new Vector3(-.10f,0,-.6f),new Vector3(.10f,0,-.6f),new Vector3(.10f,0,0),new Vector3(.32f,0,0)},triangles=new[]{0,6,1,2,4,3,2,5,4}};
        mesh.RecalculateNormals();arrow.AddComponent<MeshFilter>().mesh=mesh;arrow.SetActive(false);rt=new RenderTexture(640,400,24,RenderTextureFormat.ARGB32);
    }
    IEnumerator Start(){
        float end=Time.realtimeSinceStartup+90;
        while(ARSession.state!=ARSessionState.SessionTracking&&Time.realtimeSinceStartup<end)yield return null;
        provider=FindAnyObjectByType<SimulationCameraPoseProvider>();origin=FindAnyObjectByType<XROrigin>();
        for(int k=0;k<20;k++)yield return null;
        if(provider==null){Fail("No XR provider");yield break;}
        if(Application.isBatchMode)yield return Guard(RunAll());
    }
    IEnumerator Guard(IEnumerator it){var stack=new Stack<IEnumerator>();stack.Push(it);while(stack.Count>0){object x=null;bool more=false;try{more=stack.Peek().MoveNext();if(more)x=stack.Peek().Current;}catch(Exception e){Fail(e.ToString());yield break;}if(!more){stack.Pop();continue;}if(x is IEnumerator nested)stack.Push(nested);else yield return x;}}
    void Fail(string message){error=message;Hide();Debug.LogError("VISUAL_FAILED "+message);Finish(1);}
    void Finish(int code){
#if UNITY_EDITOR
        if(Application.isBatchMode){UnityEditor.SessionState.SetInt("AccessibleXR.ExitCode",code);UnityEditor.SessionState.SetBool("AccessibleXR.Finished",true);UnityEditor.EditorApplication.isPlaying=false;}
#endif
    }
    void Hide(){line.enabled=false;arrow.SetActive(false);}
    void Update(){if(line!=null&&(Time.realtimeSinceStartup-lastReply>1.5f||!session.enabled||ARSession.state!=ARSessionState.SessionTracking)){if(line.enabled)expired=true;Hide();}}
    IEnumerator Json(string path,object body,bool fatal=true){
        string endpoint=(label=="connection_refused"&&frame==20&&path.EndsWith("/frame"))?"http://127.0.0.1:8767":Server;
        using(var r=new UnityWebRequest(endpoint+path,"POST")){
            r.uploadHandler=new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(body)));r.downloadHandler=new DownloadHandlerBuffer();r.SetRequestHeader("Content-Type","application/json");r.timeout=fatal?30:2;
            yield return r.SendWebRequest();
            if(r.result!=UnityWebRequest.Result.Success){error="HTTP "+r.responseCode+" "+r.error;Hide();if(fatal)throw new Exception(error);yield break;}
            if(path!="/test/fault"){reply=JsonUtility.FromJson<VReply>(r.downloadHandler.text);lastReply=Time.realtimeSinceStartup;}error="";
        }
    }
    static Vector3 U(float[] p)=>new Vector3(p[0],p[1],-p[2]);
    static float[] Flat(Matrix4x4 m){var a=new float[16];for(int r=0;r<4;r++)for(int c=0;c<4;c++)a[r*4+c]=m[r,c];return a;}
    static Matrix4x4 Mat(float[] a){var m=Matrix4x4.identity;for(int r=0;r<4;r++)for(int c=0;c<4;c++)m[r,c]=a[r*4+c];return m;}
    static Matrix4x4 W()=>Matrix4x4.Scale(new Vector3(1,1,-1));
    static Matrix4x4 C()=>Matrix4x4.Scale(new Vector3(1,-1,1));
    IEnumerator Move(Vector3 p,Vector3 forward){if(forward.sqrMagnitude>.01f)viewRotation=Quaternion.LookRotation(forward)*Quaternion.Euler(12,0,0);provider.transform.SetPositionAndRotation(p,viewRotation);for(int k=0;k<5;k++)yield return null;}
    Texture2D Capture(){
        var old=arCamera.targetTexture;var active=RenderTexture.active;arCamera.targetTexture=rt;arCamera.Render();RenderTexture.active=rt;
        var t=new Texture2D(640,400,TextureFormat.RGB24,false);t.ReadPixels(new Rect(0,0,640,400),0,0);t.Apply();arCamera.targetTexture=old;RenderTexture.active=active;return t;
    }
    void Paint(){
        if(reply==null||!reply.accepted||!reply.arrow_visible||reply.pose==null||reply.pose.Length!=16||error!=""||!session.enabled||ARSession.state!=ARSessionState.SessionTracking){Hide();return;}
        // Visual map pose is estimated; local device pose supplies ONLY the render-space transform.
        // No ground-truth map alignment is read. A coordinate-origin change is handled here.
        var visualUnity=W()*Mat(reply.pose)*C();mapToXR=arCamera.transform.localToWorldMatrix*visualUnity.inverse;
        var mapPos=U(reply.position)-Vector3.up*height+Vector3.up*.08f;var target=U(reply.target);target.y=mapPos.y;
        var delta=target-mapPos;var p=mapToXR.MultiplyPoint3x4(mapPos);var end=mapToXR.MultiplyPoint3x4(mapPos+Vector3.ClampMagnitude(delta,3));
        line.enabled=true;arrow.SetActive(true);line.SetPosition(0,p);line.SetPosition(1,end);
        arrow.transform.position=mapToXR.MultiplyPoint3x4(mapPos+Vector3.ClampMagnitude(delta,1.8f));
        if(delta.sqrMagnitude>.01f)arrow.transform.rotation=mapToXR.rotation*Quaternion.LookRotation(delta);
    }
    IEnumerator Observe(string action="observe",bool blackout=false){
        clock+=.5f;expired=false;
        bool wasVisible=line.enabled;Hide();var im=Capture();
        if(blackout||label=="dim"||label=="occlusion"){
            var px=im.GetPixels();for(int y=0;y<400;y++)for(int x=0;x<640;x++){
                int j=y*640+x;if(blackout)px[j]=Color.black;
                else if(label=="dim")px[j]*=.25f;
                else if(x>160&&x<480&&y>40&&y<360)px[j]=new Color(.1f,.1f,.1f);
            }im.SetPixels(px);im.Apply();
        }
        string stem="frame-"+frame.ToString("D4");byte[] png=im.EncodeToPNG();Destroy(im);File.WriteAllBytes(Path.Combine(folder,stem+"-input.png"),png);
        // Intrinsics describe the actual projection used for the captured frame.
        var proj=arCamera.projectionMatrix;var body=new VInput{frame=frame,time_s=clock,image=Convert.ToBase64String(png),action=action,camera_height=height,resuming=transportLost,
            fx=proj[0,0]*320,fy=proj[1,1]*200,cx=(1-proj[0,2])*320-.5f,cy=(1+proj[1,2])*200-.5f};
        if(wasVisible&&reply!=null)Paint();float started=Time.realtimeSinceStartup;
        if(session.enabled&&ARSession.state==ARSessionState.SessionTracking)yield return Json("/sessions/"+sid+"/frame",body,false);
        else {error="XR session unavailable";Hide();}
        float http=(Time.realtimeSinceStartup-started)*1000;
        transportLost=error!="";
        if(error==""&&reply.frame==frame)Paint();else Hide();
        var view=Capture();File.WriteAllBytes(Path.Combine(folder,stem+"-view.jpg"),view.EncodeToJPG(88));Destroy(view);
        var row=new VRecord{frame=frame,time_s=clock,http_ms=http,camera_height=height,condition=label,action=action,input_image=stem+"-input.png",view_image=stem+"-view.jpg",
            reference_pose=Flat(W()*provider.transform.localToWorldMatrix*C()),local_xr_pose=Flat(arCamera.transform.localToWorldMatrix),map_to_xr=Flat(mapToXR),
            prediction=error==""?reply:null,transport_error=error,visible=line.enabled,expired_during_wait=expired,origin_reset=label=="origin_reset"&&frame>=25};
        File.AppendAllText(Path.Combine(folder,"observations.jsonl"),JsonUtility.ToJson(row)+"\n");frame++;
        if(frame%25==0)Debug.Log("VISUAL_OBSERVATION "+label+" "+frame+" "+(reply==null?"none":reply.state)+" "+error);
    }
    IEnumerator Begin(string name){
        label=name;height=name=="height"?1.65f:1.2f;frame=0;clock=0;transportLost=false;Hide();origin.transform.SetPositionAndRotation(Vector3.zero,Quaternion.identity);
        folder=Path.Combine(Output,"runs",Environment.GetEnvironmentVariable("WAYFINDING_VISUAL_RUN")??"development-v1",name);Directory.CreateDirectory(folder);File.WriteAllText(Path.Combine(folder,"observations.jsonl"),"");
        foreach(var env in FindObjectsByType<VisualStationEnvironment>(FindObjectsSortMode.None))env.SetRepeated(name=="repeated");
        yield return Json("/sessions",new VStart{label=name});sid=reply.session;
    }
    IEnumerator RunAll(){
        busy=true;var runs=new List<VRun>();string cases=Environment.GetEnvironmentVariable("WAYFINDING_VISUAL_CASES")??"nominal,blackout,dim,occlusion,height,repeated,network_delay,network_disconnect,origin_reset";
        foreach(string name in cases.Split(',')){
            yield return Begin(name);string predictions=reply.prediction_file;var route=reply.waypoints;
            var point=U(route[0].position)+Vector3.up*height;yield return Move(point,Vector3.back);for(int k=0;k<4;k++)yield return Observe();
            bool injected=false;
            for(int i=1;i<route.Length;i++){
                var w=route[i];var target=U(w.position)+Vector3.up*height;var delta=target-point;
                if(w.kind=="elevator"){
                    yield return Observe("board");for(int k=1;k<=10;k++){yield return Move(Vector3.Lerp(point,target,k/10f),Vector3.zero);yield return Observe();}
                    yield return Observe("exit");for(int k=0;k<5;k++)yield return Observe();
                }else{
                    int count=Mathf.CeilToInt(delta.magnitude/.55f);
                    for(int k=1;k<=count;k++){
                        var next=Vector3.Lerp(point,target,(float)k/count);yield return Move(next,delta);
                        if(name=="origin_reset"&&frame>=25&&!injected){origin.transform.SetPositionAndRotation(new Vector3(4,0,2),Quaternion.Euler(0,25,0));injected=true;for(int j=0;j<5;j++)yield return null;}
                        if((name=="network_delay"||name=="network_disconnect")&&frame>=20&&!injected){yield return Json("/test/fault",new VFault{delay_s=name=="network_delay"?4:0,status=name=="network_disconnect"?503:200});injected=true;}
                        yield return Observe();
                        if(name=="blackout"&&i==1&&k==count/2){for(int j=0;j<6;j++)yield return Observe("observe",true);for(int j=0;j<5;j++)yield return Observe();}
                    }
                    for(int k=0;k<2;k++)yield return Observe();
                }point=target;
            }
            for(int k=0;k<3;k++)yield return Observe();
            var info=new VRun{condition=name,final_state=reply.state,frames=frame,arrived=reply.state=="arrived",prediction_file=predictions};runs.Add(info);
            File.WriteAllText(Path.Combine(folder,"run.json"),JsonUtility.ToJson(info,true));
            using(var r=UnityWebRequest.Delete(Server+"/sessions/"+sid))yield return r.SendWebRequest();
            Debug.Log("VISUAL_SCENARIO_COMPLETE "+name+" "+info.final_state+" "+frame);
        }
        string dir=Path.GetDirectoryName(folder);File.WriteAllText(Path.Combine(dir,"batch.json"),JsonUtility.ToJson(new VBatch{executed=true,unity_version=Application.unityVersion,method="image-localized XR guidance",runs=runs.ToArray()},true));
        busy=false;Debug.Log("VISUAL_COMPLETE "+runs.Count);Finish(0);
    }
    IEnumerator Manual(){
        busy=true;manual=true;yield return Begin("manual-"+Guid.NewGuid().ToString("N").Substring(0,8));yield return Move(new Vector3(0,1.2f,0),Vector3.back);
        while(manual){string action=manualAction;manualAction="observe";yield return Observe(action);yield return new WaitForSecondsRealtime(.2f);}busy=false;Hide();
    }
    void OnGUI(){
        GUILayout.BeginArea(new Rect(16,16,450,360),GUI.skin.box);GUILayout.Label("IMAGE-LOCALIZED ELEVATOR GUIDANCE / SYNTHETIC");
        GUILayout.Label((reply==null?"Ready":reply.state+" / "+reply.reason)+" "+error);
        if(!busy&&provider!=null&&GUILayout.Button("Start image-based manual navigation"))StartCoroutine(Guard(Manual()));
        if(manual){
            GUILayout.Label("Right mouse + WASD; Q/E height. Buttons also move the simulated device.");
            if(GUILayout.Button("Step forward 0.5 m")){var f=provider.transform.forward;f.y=0;provider.transform.position+=f.normalized*.5f;}
            if(GUILayout.Button("Turn right 90 degrees"))provider.transform.Rotate(Vector3.up,90,Space.World);
            if(GUILayout.Button(session.enabled?"Pause XR session":"Resume XR session"))session.enabled=!session.enabled;
            if(GUILayout.Button("Confirm boarding"))manualAction="board";
            if(GUILayout.Button("Confirm exit"))manualAction="exit";
            if(GUILayout.Button("Stop"))manual=false;
        }
        GUILayout.Label("RGB only to localization server; local XR pose used for rendering");GUILayout.EndArea();
    }
}
