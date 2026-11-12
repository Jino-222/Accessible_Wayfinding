using System;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.XR.Management;
using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.Management;
using UnityEngine.XR.Simulation;
using Unity.XR.CoreUtils;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;

[InitializeOnLoad]
public static class XRDemoBuilder {
    const string Folder="Assets/XRDemo";
    const string RunKey="AccessibleXR.AutomatedRun";
    static XRDemoBuilder() { EditorApplication.update += Watch; }
    static void Watch() {
        if(!SessionState.GetBool(RunKey,false)) return;
        if(SessionState.GetBool("AccessibleXR.Finished",false) && !EditorApplication.isPlaying) {
            SessionState.SetBool(RunKey,false); EditorApplication.Exit(SessionState.GetInt("AccessibleXR.ExitCode",1));
        }
    }
    static Material Material(string name,Color color) {
        string path=Folder+"/"+name+".mat";
        var m=AssetDatabase.LoadAssetAtPath<Material>(path);
        if(m==null) {m=new Material(Shader.Find("Unlit/Color"));AssetDatabase.CreateAsset(m,path);}
        m.shader=Shader.Find("Unlit/Color");m.color=color;EditorUtility.SetDirty(m);return m;
    }
    static GameObject Box(Transform root,string name,Vector3 pos,Vector3 scale,Material mat) {
        var g=GameObject.CreatePrimitive(PrimitiveType.Cube);g.name=name;g.transform.SetParent(root);
        g.transform.position=pos;g.transform.localScale=scale;g.GetComponent<Renderer>().sharedMaterial=mat;return g;
    }
    static void Label(Transform root,string text,Vector3 pos,Quaternion rotation,float size=.18f) {
        var g=new GameObject(text);g.transform.SetParent(root);g.transform.position=pos;g.transform.rotation=rotation*Quaternion.Euler(0,180,0);
        var t=g.AddComponent<TextMesh>();t.text=text;t.fontSize=56;t.characterSize=size*.35f;t.anchor=TextAnchor.MiddleCenter;
        t.color=Color.white;t.font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        g.GetComponent<MeshRenderer>().sharedMaterial=t.font.material;
    }
    static UnityEngine.Object Setting(Type type) {
        return (UnityEngine.Object)type.GetProperty("Instance",BindingFlags.Public|BindingFlags.Static|BindingFlags.FlattenHierarchy).GetValue(null);
    }
    [MenuItem("Accessible Station/Build XR demo")]
    public static void Build() {
        Directory.CreateDirectory(Folder);AssetDatabase.Refresh();
        var so=new SerializedObject(Resources.FindObjectsOfTypeAll<PlayerSettings>()[0]);
        so.FindProperty("activeInputHandler").intValue=2;so.ApplyModifiedPropertiesWithoutUndo();
        var per=AssetDatabase.LoadAssetAtPath<XRGeneralSettingsPerBuildTarget>(Folder+"/XRSettings.asset");
        if(per==null) {per=ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();AssetDatabase.CreateAsset(per,Folder+"/XRSettings.asset");}
        if(!per.HasSettingsForBuildTarget(BuildTargetGroup.Standalone))per.CreateDefaultManagerSettingsForBuildTarget(BuildTargetGroup.Standalone);
        var general=per.SettingsForBuildTarget(BuildTargetGroup.Standalone);
        general.InitManagerOnStart=true;
        var loader=AssetDatabase.LoadAssetAtPath<SimulationLoader>(Folder+"/SimulationLoader.asset");
        if(loader==null) {loader=ScriptableObject.CreateInstance<SimulationLoader>();AssetDatabase.CreateAsset(loader,Folder+"/SimulationLoader.asset");}
        bool assigned=false;foreach(var current in general.Manager.activeLoaders)if(current==loader)assigned=true;
        if(!assigned&&!general.Manager.TryAddLoader(loader))throw new Exception("Cannot add XR Simulation loader");
        EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey,per,true);
        EditorUtility.SetDirty(per);EditorUtility.SetDirty(general);EditorUtility.SetDirty(general.Manager);
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var environment=new GameObject("Accessible two-floor station");
        var floor=Material("Floor",new Color(.73f,.77f,.79f));var wall=Material("Wall",new Color(.86f,.86f,.83f));
        var blue=Material("B2Blue",new Color(.05f,.28f,.40f));var ochre=Material("B1Ochre",new Color(.45f,.29f,.08f));
        var metal=Material("Lift",new Color(.27f,.36f,.39f));
        var spec=JsonUtility.FromJson<ResearchScene>(File.ReadAllText(Path.Combine(Application.streamingAssetsPath,"research-scene.json")));
        var occupied=new System.Collections.Generic.HashSet<string>();
        foreach(var c in spec.cells)occupied.Add(c.level+":"+c.x+":"+c.z);
        int[,] dirs={{1,0},{-1,0},{0,1},{0,-1}};
        foreach(var c in spec.cells) {
            var pos=new Vector3(c.x*.5f,c.y-.06f,-c.z*.5f);
            Box(environment.transform,"Floor "+c.level,pos,new Vector3(.5f,.12f,.5f),floor);
            Box(environment.transform,"Ceiling "+c.level,pos+Vector3.up*3.16f,new Vector3(.5f,.12f,.5f),wall);
            for(int d=0;d<4;d++) {
                int dx=dirs[d,0],dz=dirs[d,1];if(occupied.Contains(c.level+":"+(c.x+dx)+":"+(c.z+dz)))continue;
                var wp=new Vector3(c.x*.5f+dx*.25f,c.y+1.5f,-c.z*.5f-dz*.25f);
                var ws=new Vector3(dx!=0?.08f:.5f,3f,dz!=0?.08f:.5f);
                Box(environment.transform,"Wall",wp,ws,wall);
                Box(environment.transform,"Floor color band",new Vector3(wp.x,c.y+1.75f,wp.z),new Vector3(ws.x+.015f,.23f,ws.z+.015f),c.level=="B2"?blue:ochre);
            }
        }
        foreach(var n in spec.nodes) {
            if(!n.id.StartsWith("e1_")&&!n.id.StartsWith("e2_"))continue;
            var pos=new Vector3(n.position[0],n.position[1],-n.position[2]);bool left=n.id.StartsWith("e1_");
            Box(environment.transform,"Lift landing "+n.id,pos+new Vector3(0,.03f,0),new Vector3(1.4f,.06f,1.4f),metal);
            var r=Quaternion.Euler(0,left?90:-90,0);
            var panel=Box(environment.transform,"Lift sign",pos+new Vector3(left?-.8f:.8f,2.0f,0),new Vector3(.06f,.65f,1.7f),blue);
            Label(environment.transform,(left?"E1":"E2")+"  LIFT",panel.transform.position+new Vector3(left?.04f:-.04f,0,0),r);
        }
        Label(environment.transform,"B2   ELEVATORS",new Vector3(0,2.25f,-11.35f),Quaternion.identity,.12f);
        Label(environment.transform,"B1   DESTINATION",new Vector3(0,6.6f,-25.3f),Quaternion.identity,.12f);
        var light=new GameObject("Station lighting");light.transform.SetParent(environment.transform);light.transform.rotation=Quaternion.Euler(50,30,0);
        var li=light.AddComponent<Light>();li.type=LightType.Directional;li.intensity=.8f;
        var asm=typeof(SimulationLoader).Assembly;
        var runtimeSettings=Setting(asm.GetType("UnityEngine.XR.Simulation.XRSimulationRuntimeSettings",true));
        var scanField=runtimeSettings.GetType().GetField("m_EnvironmentScanParams",BindingFlags.NonPublic|BindingFlags.Instance);
        if(scanField.GetValue(runtimeSettings)==null)scanField.SetValue(runtimeSettings,Activator.CreateInstance(scanField.FieldType,true));
        EditorUtility.SetDirty(runtimeSettings);AssetDatabase.SaveAssetIfDirty(runtimeSettings);
        var env=environment.AddComponent(asm.GetType("UnityEngine.XR.Simulation.SimulationEnvironment",true));
        var es=new SerializedObject(env);
        es.FindProperty("m_CameraStartingPose.position").vector3Value=new Vector3(0,1.2f,0);
        es.FindProperty("m_CameraStartingPose.rotation").quaternionValue=Quaternion.Euler(0,180,0);
        es.FindProperty("m_CameraMovementBounds").boundsValue=new Bounds(new Vector3(2,4,-12),new Vector3(50,15,60));
        es.ApplyModifiedPropertiesWithoutUndo();
        var prefab=PrefabUtility.SaveAsPrefabAsset(environment,Folder+"/StationEnvironment.prefab");
        UnityEngine.Object.DestroyImmediate(environment);
        var pref=Setting(asm.GetType("UnityEngine.XR.Simulation.XRSimulationPreferences",true));
        var ps=new SerializedObject(pref);ps.FindProperty("m_EnvironmentPrefab").objectReferenceValue=prefab;ps.ApplyModifiedPropertiesWithoutUndo();EditorUtility.SetDirty(pref);
        var session=new GameObject("AR Session");session.AddComponent<ARSession>();session.AddComponent<ARInputManager>();
        var originGo=new GameObject("XR Origin");var origin=originGo.AddComponent<XROrigin>();
        var offset=new GameObject("Camera Offset");offset.transform.SetParent(originGo.transform);
        origin.CameraFloorOffsetObject=offset;origin.CameraYOffset=0;origin.RequestedTrackingOriginMode=XROrigin.TrackingOriginMode.Floor;
        var cameraGo=new GameObject("AR Camera");cameraGo.tag="MainCamera";cameraGo.transform.SetParent(offset.transform);
        var camera=cameraGo.AddComponent<Camera>();camera.nearClipPlane=.05f;camera.farClipPlane=80;camera.fieldOfView=62;camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=Color.black;
        origin.Camera=camera;cameraGo.AddComponent<ARCameraManager>();cameraGo.AddComponent<ARCameraBackground>();
        var driver=cameraGo.AddComponent<TrackedPoseDriver>();
        var positionAction=new InputAction("Position",InputActionType.Value,"<XRHMD>/centerEyePosition",expectedControlType:"Vector3");
        positionAction.AddBinding("<HandheldARInputDevice>/devicePosition");
        var rotationAction=new InputAction("Rotation",InputActionType.Value,"<XRHMD>/centerEyeRotation",expectedControlType:"Quaternion");
        rotationAction.AddBinding("<HandheldARInputDevice>/deviceRotation");
        var trackingAction=new InputAction("Tracking",InputActionType.Value,"<XRHMD>/trackingState",expectedControlType:"Integer");
        trackingAction.AddBinding("<HandheldARInputDevice>/trackingState");
        driver.positionInput=new InputActionProperty(positionAction);driver.rotationInput=new InputActionProperty(rotationAction);
        driver.trackingStateInput=new InputActionProperty(trackingAction);
        var demo=new GameObject("Elevator guidance demo").AddComponent<XRWalkthrough>();
        demo.arCamera=camera;demo.session=session.GetComponent<ARSession>();
        RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;RenderSettings.ambientLight=new Color(.8f,.8f,.8f);
        EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(),Folder+"/XRStationDemo.unity");
        AssetDatabase.SaveAssets();Debug.Log("XR_DEMO_BUILT");
    }
    public static void BuildAndRun() {
        Build();SessionState.SetBool(RunKey,true);SessionState.SetBool("AccessibleXR.Finished",false);
        EditorApplication.EnterPlaymode();
    }
}

