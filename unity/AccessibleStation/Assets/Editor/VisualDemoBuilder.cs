using System;
using System.IO;
using System.Reflection;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.Simulation;

public static class VisualDemoBuilder {
    const string SpecPath="Assets/StreamingAssets/visual-scene.json";
    public static void CaptureMap(){
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var text=File.ReadAllText(SpecPath);var spec=JsonUtility.FromJson<VSpec>(text);
        Directory.CreateDirectory(spec.output);
        var env=new GameObject("Visual mapping environment").AddComponent<VisualStationEnvironment>();env.specificationJson=text;env.Build();
        var cam=new GameObject("Map camera").AddComponent<Camera>();cam.fieldOfView=spec.fov;cam.aspect=(float)spec.width/spec.height;
        cam.nearClipPlane=.05f;cam.farClipPlane=80;cam.backgroundColor=new Color(.06f,.09f,.12f);cam.clearFlags=CameraClearFlags.SolidColor;
        cam.allowHDR=false;cam.allowMSAA=false;
        var rt=new RenderTexture(spec.width,spec.height,24,RenderTextureFormat.ARGB32);cam.targetTexture=rt;
        var records=new List<ViewRecord>();Physics.SyncTransforms();
        foreach(var v in spec.mapping){
            cam.transform.position=new Vector3(v.position[0],v.position[1],-v.position[2]);cam.transform.rotation=Quaternion.Euler(v.pitch,v.yaw,0);
            cam.Render();RenderTexture.active=rt;var im=new Texture2D(spec.width,spec.height,TextureFormat.RGB24,false);
            im.ReadPixels(new Rect(0,0,spec.width,spec.height),0,0);im.Apply();File.WriteAllBytes(Path.Combine(spec.output,v.id+".png"),im.EncodeToPNG());UnityEngine.Object.DestroyImmediate(im);
            using(var w=new BinaryWriter(File.Open(Path.Combine(spec.output,v.id+".depth"),FileMode.Create))){
                for(int y=0;y<spec.height;y++)for(int x=0;x<spec.width;x++){
                    var ray=cam.ScreenPointToRay(new Vector3(x+.5f,spec.height-y-.5f,0));float z=0;
                    if(Physics.Raycast(ray,out var hit,80))z=Vector3.Dot(hit.point-cam.transform.position,cam.transform.forward);w.Write(z);
                }
            }
            float[] pose=new float[16];float[] ws={1,1,-1,1},cs={1,-1,1,1};var m=cam.transform.localToWorldMatrix;
            for(int r=0;r<4;r++)for(int c=0;c<4;c++)pose[r*4+c]=ws[r]*m[r,c]*cs[c];
            float f=spec.height/(2*Mathf.Tan(spec.fov*Mathf.Deg2Rad/2));
            records.Add(new ViewRecord{id=v.id,split="mapping",image=v.id+".png",depth=v.id+".depth",camera_to_world=pose,width=spec.width,height=spec.height,fx=f,fy=f,cx=(spec.width-1)/2f,cy=(spec.height-1)/2f});
            if(records.Count%20==0)Debug.Log("VISUAL_MAP_CAPTURE "+records.Count);
        }
        File.WriteAllText(Path.Combine(spec.output,"manifest.json"),JsonUtility.ToJson(new CaptureManifest{scene_revision="visual-runtime-v1",records=records.ToArray()},true));
        RenderTexture.active=null;cam.targetTexture=null;rt.Release();Debug.Log("VISUAL_MAP_COMPLETE "+records.Count);
    }
    [MenuItem("Accessible Station/Build image-localized XR demo")]
    public static void Build(){
        XRDemoBuilder.Build();
        UnityEngine.Object.DestroyImmediate(UnityEngine.Object.FindAnyObjectByType<XRWalkthrough>().gameObject);
        var root=new GameObject("Image-localized station");
        var generator=root.AddComponent<VisualStationEnvironment>();generator.specificationJson=File.ReadAllText(SpecPath);
        var asm=typeof(SimulationLoader).Assembly;
        var e=root.AddComponent(asm.GetType("UnityEngine.XR.Simulation.SimulationEnvironment",true));var es=new SerializedObject(e);
        es.FindProperty("m_CameraStartingPose.position").vector3Value=new Vector3(0,1.2f,0);
        es.FindProperty("m_CameraStartingPose.rotation").quaternionValue=Quaternion.Euler(12,180,0);
        es.FindProperty("m_CameraMovementBounds").boundsValue=new Bounds(new Vector3(2,4,-12),new Vector3(50,15,60));es.ApplyModifiedPropertiesWithoutUndo();
        var prefab=PrefabUtility.SaveAsPrefabAsset(root,"Assets/XRDemo/VisualEnvironment.prefab");UnityEngine.Object.DestroyImmediate(root);
        var type=asm.GetType("UnityEngine.XR.Simulation.XRSimulationPreferences",true);
        var pref=(UnityEngine.Object)type.GetProperty("Instance",BindingFlags.Public|BindingFlags.Static|BindingFlags.FlattenHierarchy).GetValue(null);
        var ps=new SerializedObject(pref);ps.FindProperty("m_EnvironmentPrefab").objectReferenceValue=prefab;ps.ApplyModifiedPropertiesWithoutUndo();EditorUtility.SetDirty(pref);
        var demo=new GameObject("Image localization navigation").AddComponent<VisualWalkthrough>();demo.arCamera=Camera.main;demo.session=UnityEngine.Object.FindAnyObjectByType<ARSession>();
        EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(),"Assets/XRDemo/VisualStationDemo.unity");AssetDatabase.SaveAssets();
    }
    public static void BuildAndRun(){Build();SessionState.SetBool("AccessibleXR.AutomatedRun",true);SessionState.SetBool("AccessibleXR.Finished",false);EditorApplication.EnterPlaymode();}
}
