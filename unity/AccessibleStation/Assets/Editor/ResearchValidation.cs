using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using System;
using System.IO;
using System.Collections.Generic;

[Serializable] public class CalibrationMarker {
    public string name; public float[] world,opencv_pixel; public int[] rgb;
}
[Serializable] public class CalibrationResult {
    public float[] camera_to_world; public float fx,fy,cx,cy;
    public int width,height; public CalibrationMarker[] markers;
}

public static class ResearchValidation {
    public static void Run() {
        var spec=JsonUtility.FromJson<ResearchScene>(File.ReadAllText(
            Path.Combine(Application.streamingAssetsPath,"research-scene.json")));
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var camera=new GameObject("Calibration camera").AddComponent<Camera>();
        camera.transform.position=new Vector3(1.25f,2.35f,-3.15f);
        camera.transform.rotation=Quaternion.Euler(11,29,-7);
        camera.fieldOfView=spec.vertical_fov;camera.aspect=(float)spec.width/spec.height;
        camera.nearClipPlane=.05f;camera.farClipPlane=80;
        camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=Color.black;
        camera.allowHDR=false;camera.allowMSAA=false;
        var target=new RenderTexture(spec.width,spec.height,24,RenderTextureFormat.ARGB32,RenderTextureReadWrite.Linear);
        camera.targetTexture=target;
        var centers=new Vector3[]{new Vector3(-1.35f,.85f,5),new Vector3(.85f,1.1f,6),
            new Vector3(1.25f,-.8f,4.7f),new Vector3(-.75f,-.65f,5.3f)};
        var colors=new Color[]{Color.red,Color.green,Color.blue,Color.yellow};
        var names=new string[]{"red-upper-left","green-upper-right","blue-lower-right","yellow-lower-left"};
        var markers=new List<CalibrationMarker>();
        var shader=Shader.Find("Unlit/Color");if(shader==null)throw new Exception("Missing calibration shader");
        for(int i=0;i<centers.Length;i++) {
            var obj=GameObject.CreatePrimitive(PrimitiveType.Quad);obj.name=names[i];
            obj.transform.position=camera.transform.TransformPoint(centers[i]);
            obj.transform.rotation=camera.transform.rotation;obj.transform.localScale=new Vector3(.35f,.35f,1);
            var material=new Material(shader);material.color=colors[i];obj.GetComponent<Renderer>().sharedMaterial=material;
            var world=obj.transform.position;var screen=camera.WorldToScreenPoint(world);
            markers.Add(new CalibrationMarker{name=names[i],world=new float[]{world.x,world.y,-world.z},
                opencv_pixel=new float[]{screen.x-.5f,spec.height-.5f-screen.y},
                rgb=new int[]{Mathf.RoundToInt(colors[i].r*255),Mathf.RoundToInt(colors[i].g*255),Mathf.RoundToInt(colors[i].b*255)}});
        }
        camera.Render();RenderTexture.active=target;
        var texture=new Texture2D(spec.width,spec.height,TextureFormat.RGB24,false,true);
        texture.ReadPixels(new Rect(0,0,spec.width,spec.height),0,0);texture.Apply();
        File.WriteAllBytes(Path.Combine(spec.output,"calibration.png"),texture.EncodeToPNG());
        var transform=camera.transform.localToWorldMatrix;float[] pose=new float[16],ws={1,1,-1,1},cs={1,-1,1,1};
        for(int r=0;r<4;r++)for(int c=0;c<4;c++)pose[r*4+c]=ws[r]*transform[r,c]*cs[c];
        float f=spec.height/(2*Mathf.Tan(spec.vertical_fov*Mathf.Deg2Rad/2));
        var result=new CalibrationResult{camera_to_world=pose,width=spec.width,height=spec.height,
            fx=f,fy=f,cx=(spec.width-1)/2f,cy=(spec.height-1)/2f,markers=markers.ToArray()};
        File.WriteAllText(Path.Combine(spec.output,"calibration.json"),JsonUtility.ToJson(result,true));
        RenderTexture.active=null;target.Release();UnityEngine.Object.DestroyImmediate(texture);
        Debug.Log("RESEARCH_CALIBRATION_COMPLETE "+markers.Count);
    }
}
