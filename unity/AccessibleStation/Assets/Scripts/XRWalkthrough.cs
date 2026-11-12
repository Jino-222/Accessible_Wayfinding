using System;
using System.IO;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.XR;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.Management;
using UnityEngine.XR.Simulation;

[Serializable] public class XRWaypoint { public string node,kind,floor; public float[] position; }
[Serializable] public class XRReply {
    public string session,state,reason,current_node,pose_source;public bool arrow_visible;
    public float[] target;public int recovery_count,step_index;public XRWaypoint[] waypoints;
}
[Serializable] public class XRStart { public string scenario; }
[Serializable] public class XRSample { public float time_s;public float[] position;public string floor,action;public bool tracking; }
[Serializable] public class XRFrame {
    public string scenario,state,reason,floor,action,session_state,device,frame_image;
    public int frame,recovery_count,camera_frames;public float time_s;
    public bool arrow_visible,session_running,device_tracked,tracking,session_pause_injected,floor_fault_injected;
    public float[] position,requested_position,target;public float pose_transport_error_m;
}
[Serializable] public class XRRunInfo {
    public string scenario,unity_version,arfoundation_version,loader,session_subsystem,camera_subsystem,environment;
    public int frames,camera_frames;public bool completed;public string final_state;
}
[Serializable] public class XRBatchInfo { public bool completed;public string error;public XRRunInfo[] runs; }

public class XRWalkthrough : MonoBehaviour {
    public Camera arCamera;
    public ARSession session;
    public string server="http://127.0.0.1:8765";
    public bool manualMovement;
    readonly string[] scenarios={"normal","tracking_loss","elevator_loss","wrong_floor","alternate_elevator"};
    SimulationCameraPoseProvider provider;
    XRReply reply;
    string sid,scenario,folder,error="";
    float logicalTime;
    float lastReplyRealtime=-100;
    int frame,cameraFrames;
    bool busy,finished,recording;
    bool manualRide;
    string manualAction="observe";
    Vector3 requested;
    Quaternion viewRotation=Quaternion.Euler(0,180,0);
    LineRenderer line;
    GameObject arrow;
    RenderTexture render;
    List<XRRunInfo> runs=new List<XRRunInfo>();
    string Output => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"AccessibleWayfinding","research","xr-simulation");
    void Awake() {
        Application.runInBackground=true;QualitySettings.vSyncCount=0;
        arCamera.GetComponent<ARCameraManager>().frameReceived += CameraFrame;
        var mat=new Material(Shader.Find("Unlit/Color"));mat.color=new Color(.05f,.85f,.70f);
        line=new GameObject("Live route line").AddComponent<LineRenderer>();line.material=mat;line.startWidth=.09f;line.endWidth=.09f;line.positionCount=2;line.enabled=false;
        arrow=new GameObject("Route arrow");var mesh=arrow.AddComponent<MeshFilter>();arrow.AddComponent<MeshRenderer>().material=mat;
        mesh.mesh=new Mesh {vertices=new []{new Vector3(0,0,.7f),new Vector3(-.32f,0,0),new Vector3(-.10f,0,0),new Vector3(-.10f,0,-.6f),new Vector3(.10f,0,-.6f),new Vector3(.10f,0,0),new Vector3(.32f,0,0)},triangles=new []{0,6,1,2,4,3,2,5,4}};
        mesh.mesh.RecalculateNormals();arrow.SetActive(false);
        render=new RenderTexture(800,500,24,RenderTextureFormat.ARGB32);
    }
    void CameraFrame(ARCameraFrameEventArgs e) {cameraFrames++;}
    IEnumerator Start() {
        float deadline=Time.realtimeSinceStartup+60;
        while((ARSession.state!=ARSessionState.SessionTracking || cameraFrames<2) && Time.realtimeSinceStartup<deadline)yield return null;
        provider=FindAnyObjectByType<SimulationCameraPoseProvider>();
        if(provider==null||ARSession.state!=ARSessionState.SessionTracking) {Fail("XR provider/session did not start");yield break;}
        Debug.Log("XR_RUNTIME_READY "+XRGeneralSettings.Instance.Manager.activeLoader.name+" "+cameraFrames);
        if(Application.isBatchMode)yield return Guard(RunAll());
    }
    IEnumerator Guard(IEnumerator iterator) {
        var stack=new Stack<IEnumerator>();stack.Push(iterator);
        while(stack.Count>0) {
            bool more=false;object value=null;
            try {more=stack.Peek().MoveNext();if(more)value=stack.Peek().Current;}
            catch(Exception e) {Fail(e.ToString());yield break;}
            if(!more){stack.Pop();continue;}
            if(value is IEnumerator nested)stack.Push(nested);
            else yield return value;
        }
    }
    void Fail(string message) {
        error=message;Debug.LogError("XR_DEMO_FAILED "+message);busy=false;manualMovement=false;
        line.enabled=false;arrow.SetActive(false);
        Directory.CreateDirectory(Output);File.WriteAllText(Path.Combine(Output,"run-complete.json"),JsonUtility.ToJson(new XRBatchInfo{completed=false,error=message,runs=runs.ToArray()},true));
        FinishEditor(1);
    }
    void FinishEditor(int exitCode) {
#if UNITY_EDITOR
        if(Application.isBatchMode) {
            UnityEditor.SessionState.SetInt("AccessibleXR.ExitCode",exitCode);
            UnityEditor.SessionState.SetBool("AccessibleXR.Finished",true);
            UnityEditor.EditorApplication.isPlaying=false;
        }
#endif
    }
    IEnumerator Post(string path,object body) {
        using(var req=new UnityWebRequest(server+path,"POST")) {
            req.uploadHandler=new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(body)));req.downloadHandler=new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type","application/json");req.timeout=10;yield return req.SendWebRequest();
            if(req.result!=UnityWebRequest.Result.Success)throw new Exception("Bridge "+req.responseCode+": "+req.downloadHandler.text);
            reply=JsonUtility.FromJson<XRReply>(req.downloadHandler.text);
            lastReplyRealtime=Time.realtimeSinceStartup;
        }
    }
    static Vector3 U(float[] a) {return new Vector3(a[0],a[1],-a[2]);}
    static float[] P(Vector3 p) {return new []{p.x,p.y,-p.z};}
    bool DeviceTracked(out string name) {
        var device=InputDevices.GetDeviceAtXRNode(XRNode.CenterEye);name=device.name;
        bool tracked=false;InputTrackingState state;
        return device.isValid&&device.TryGetFeatureValue(CommonUsages.isTracked,out tracked)&&tracked&&
            device.TryGetFeatureValue(CommonUsages.trackingState,out state)&&(state&InputTrackingState.Position)!=0&&(state&InputTrackingState.Rotation)!=0;
    }
    IEnumerator Position(Vector3 point,Vector3 forward) {
        requested=point;
        if(forward.sqrMagnitude>.01f)viewRotation=Quaternion.LookRotation(forward,Vector3.up)*Quaternion.Euler(12,0,0);
        // Set the provider's simulated device, never the tracked AR camera. Its input
        // update publishes the pose through XRSimulation-Input and TrackedPoseDriver.
        provider.transform.SetPositionAndRotation(point,viewRotation);
        for(int i=0;i<4;i++)yield return null;
    }
    IEnumerator Observe(string floor,string action="observe",bool floorFault=false) {
        logicalTime+=.25f;
        bool tracked=DeviceTracked(out string name);
        bool running=session.enabled&&session.subsystem!=null&&session.subsystem.running;
        bool valid=running&&ARSession.state==ARSessionState.SessionTracking&&tracked;
        var body=new XRSample{time_s=logicalTime,position=P(arCamera.transform.position),floor=floor,tracking=valid,action=action};
        yield return Post("/api/ar-research/xr/sessions/"+sid+"/sample",body);
        PaintRoute();
        // Let the background camera and AR managers render the current pose.
        yield return null;
        var filename="frame-"+frame.ToString("D4")+".jpg";
        if(recording)Capture(Path.Combine(folder,filename));
        var row=new XRFrame{scenario=scenario,frame=frame,time_s=logicalTime,position=body.position,requested_position=P(requested),target=reply.target,
            state=reply.state,reason=reply.reason,floor=floor,action=action,session_state=ARSession.state.ToString(),
            device=name,session_running=running,device_tracked=tracked,tracking=valid,session_pause_injected=!session.enabled,
            floor_fault_injected=floorFault,arrow_visible=line.enabled,recovery_count=reply.recovery_count,
            pose_transport_error_m=Vector3.Distance(arCamera.transform.position,requested),camera_frames=cameraFrames,frame_image=filename};
        if(recording)File.AppendAllText(Path.Combine(folder,"frames.jsonl"),JsonUtility.ToJson(row)+"\n");
        frame++;
    }
    void PaintRoute() {
        line.enabled=reply!=null&&reply.arrow_visible&&session.enabled&&ARSession.state==ARSessionState.SessionTracking;
        arrow.SetActive(line.enabled);
        if(!line.enabled)return;
        var pos=arCamera.transform.position-Vector3.up*1.2f;pos.y+=.08f;
        var target=U(reply.target);target.y=pos.y;
        var delta=target-pos;var end=pos+Vector3.ClampMagnitude(delta,3.0f);
        line.SetPosition(0,pos);line.SetPosition(1,end);
        if(delta.sqrMagnitude>.01f){arrow.transform.position=pos+Vector3.ClampMagnitude(delta,1.8f);arrow.transform.rotation=Quaternion.LookRotation(delta);}
    }
    void Capture(string path) {
        var previous=arCamera.targetTexture;var active=RenderTexture.active;
        arCamera.targetTexture=render;arCamera.Render();RenderTexture.active=render;
        var tex=new Texture2D(800,500,TextureFormat.RGB24,false);tex.ReadPixels(new Rect(0,0,800,500),0,0);tex.Apply();
        File.WriteAllBytes(path,tex.EncodeToJPG(85));Destroy(tex);arCamera.targetTexture=previous;RenderTexture.active=active;
    }
    void Update() {
        if(line==null)return;
        if(!session.enabled||ARSession.state!=ARSessionState.SessionTracking||Time.realtimeSinceStartup-lastReplyRealtime>1.5f) {
            line.enabled=false;arrow.SetActive(false);
        }
    }
    IEnumerator RunAll() {
        busy=true;manualMovement=false;recording=true;
        foreach(var s in scenarios)yield return RunScenario(s);
        Directory.CreateDirectory(Output);File.WriteAllText(Path.Combine(Output,"run-complete.json"),JsonUtility.ToJson(new XRBatchInfo{completed=true,runs=runs.ToArray()},true));
        finished=true;busy=false;Debug.Log("XR_DEMO_COMPLETE "+runs.Count);FinishEditor(0);
    }
    IEnumerator RunScenario(string selected) {
        scenario=selected;logicalTime=0;frame=0;folder=Path.Combine(Output,"runs",scenario);Directory.CreateDirectory(folder);
        File.WriteAllText(Path.Combine(folder,"frames.jsonl"),"");session.enabled=true;
        yield return Post("/api/ar-research/xr/sessions",new XRStart{scenario=scenario});
        sid=reply.session;var route=reply.waypoints;
        var point=U(route[0].position)+Vector3.up*1.2f;
        yield return Position(point,Vector3.back);for(int k=0;k<4;k++)yield return Observe("B2");
        for(int i=1;i<route.Length;i++) {
            var w=route[i];var target=U(w.position)+Vector3.up*1.2f;var delta=target-point;
            if(w.kind=="elevator") {
                yield return Observe("B2","board");
                if(scenario=="elevator_loss")session.enabled=false;
                int steps=20;
                for(int k=1;k<=steps;k++) {
                    var next=Vector3.Lerp(point,target,(float)k/steps);
                    // While paused the provider is inactive; the last AR pose remains stale.
                    yield return Position(next,Vector3.zero);yield return Observe("B2");
                }
                session.enabled=true;yield return Position(target,Vector3.zero);
                for(int k=0;k<6;k++)yield return null;
                yield return Observe(scenario=="wrong_floor"?"B2":"B1","exit",scenario=="wrong_floor");
                if(scenario=="wrong_floor")for(int k=0;k<4;k++)yield return Observe("B2","observe",true);
                for(int k=0;k<5;k++)yield return Observe("B1");
            } else {
                int count=Mathf.CeilToInt(delta.magnitude/.28f);
                for(int k=1;k<=count;k++) {
                    var next=Vector3.Lerp(point,target,(float)k/count);
                    yield return Position(next,delta);yield return Observe(w.floor);
                    if(scenario=="tracking_loss"&&i==1&&k==count/2) {
                        session.enabled=false;for(int j=0;j<6;j++){yield return null;yield return Observe(w.floor);}
                        session.enabled=true;yield return Position(next,delta);
                        for(int j=0;j<6;j++){yield return null;yield return Observe(w.floor);}
                    }
                }
            }
            point=target;
        }
        for(int k=0;k<3;k++)yield return Observe("B1");
        var loader=XRGeneralSettings.Instance.Manager.activeLoader;
        var info=new XRRunInfo{scenario=scenario,unity_version=Application.unityVersion,arfoundation_version="6.3.5",
            loader=loader.GetType().FullName,session_subsystem=session.subsystem.subsystemDescriptor.id,
            camera_subsystem=arCamera.GetComponent<ARCameraManager>().subsystem.subsystemDescriptor.id,
            environment="StationEnvironment",frames=frame,camera_frames=cameraFrames,completed=reply.state=="arrived",final_state=reply.state};
        runs.Add(info);File.WriteAllText(Path.Combine(folder,"run.json"),JsonUtility.ToJson(info,true));
        using(var req=UnityWebRequest.Delete(server+"/api/ar-research/xr/sessions/"+sid)){yield return req.SendWebRequest();}
        Debug.Log("XR_SCENARIO_COMPLETE "+scenario+" "+reply.state+" "+frame);
        if(!info.completed)throw new Exception("Scenario did not arrive: "+scenario+" "+reply.reason);
    }
    IEnumerator RunManual() {
        busy=true;manualMovement=true;recording=false;scenario="normal";logicalTime=0;frame=0;
        session.enabled=true;manualAction="observe";manualRide=false;
        yield return Post("/api/ar-research/xr/sessions",new XRStart{scenario="normal"});sid=reply.session;
        Vector3 liftExit=Vector3.zero;foreach(var w in reply.waypoints)if(w.kind=="elevator")liftExit=U(w.position)+Vector3.up*1.2f;
        yield return Position(new Vector3(0,1.2f,0),Vector3.back);
        while(manualMovement) {
            if(manualRide&&reply.state=="in_transit") {
                manualRide=false;var from=provider.transform.position;
                for(int i=1;i<=20;i++) {
                    yield return Position(Vector3.Lerp(from,liftExit,i/20f),Vector3.zero);
                    yield return Observe("B2");yield return new WaitForSecondsRealtime(.25f);
                }
                yield return Observe("B1","exit");
            } else {
                requested=provider.transform.position;
                var action=manualAction;manualAction="observe";
                yield return Observe(arCamera.transform.position.y>3?"B1":"B2",action);
            }
            yield return new WaitForSecondsRealtime(.25f);
        }
        using(var req=UnityWebRequest.Delete(server+"/api/ar-research/xr/sessions/"+sid)){yield return req.SendWebRequest();}
        line.enabled=false;arrow.SetActive(false);busy=false;
    }
    void OnGUI() {
        GUILayout.BeginArea(new Rect(16,16,420,350),GUI.skin.box);
        GUILayout.Label("ACCESSIBLE STATION / XR SIMULATION");
        GUILayout.Label("Synthetic scene · simulated tracking · no field validation");
        GUILayout.Label("AR: "+ARSession.state+" / camera frames "+cameraFrames);
        GUILayout.Label((scenario??"Ready")+" / "+(reply==null?"":reply.state+" · "+reply.reason));
        if(!busy && provider!=null && GUILayout.Button("Run all five recorded scenarios"))StartCoroutine(Guard(RunAll()));
        if(!busy && provider!=null && GUILayout.Button("Start manual navigation"))StartCoroutine(Guard(RunManual()));
        if(manualMovement) {
            GUILayout.Label("Hold right mouse + WASD. Q/E: height. Simulated free camera.");
            if(reply!=null&&reply.state=="awaiting_transit"&&GUILayout.Button("Confirm elevator boarding"))manualAction="board";
            if(reply!=null&&reply.state=="in_transit"&&GUILayout.Button("Move elevator to B1"))manualRide=true;
            if(GUILayout.Button("Stop manual navigation"))manualMovement=false;
        }
        if(busy && GUILayout.Button(session.enabled?"Pause XR session":"Resume XR session"))session.enabled=!session.enabled;
        if(error!="")GUILayout.Label(error);
        GUILayout.Label("Green arrow: live Python guidance from tracked XR camera.");
        GUILayout.EndArea();
    }
    void OnDestroy() {if(render!=null){render.Release();Destroy(render);}}
}

