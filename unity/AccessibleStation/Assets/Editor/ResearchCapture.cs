using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using System;
using System.IO;
using System.Collections.Generic;

[Serializable] public class FloorCell { public int x,z; public float y; public string level; }
[Serializable] public class Capture { public string id,split,floor; public float[] position; public float yaw; }
[Serializable] public class SceneNode { public string id; public float[] position; }
[Serializable] public class ResearchScene {
    public string scene_revision,output; public FloorCell[] cells; public Capture[] captures;
    public SceneNode[] nodes; public int width,height; public float vertical_fov;
}
[Serializable] public class ViewRecord {
    public string id,split,floor,image,depth; public float[] camera_to_world;
    public int width,height; public float fx,fy,cx,cy;
}
[Serializable] public class CaptureManifest { public string scene_revision; public ViewRecord[] records; }

public static class ResearchCapture {
    // Internal +Z is backward. Unity's left-handed world uses reflected Z.
    static Vector3 ToUnity(float[] p) { return new Vector3(p[0],p[1],-p[2]); }
    static Material Surface(Color color) {
        var m=new Material(Shader.Find("Standard")); m.color=color;
        m.SetFloat("_Glossiness",0.12f); return m;
    }
    static GameObject Box(string name,Vector3 position,Vector3 scale,Material material) {
        var obj=GameObject.CreatePrimitive(PrimitiveType.Cube);obj.name=name;
        obj.transform.position=position;obj.transform.localScale=scale;
        obj.GetComponent<Renderer>().sharedMaterial=material;return obj;
    }
    static Material Pattern(int seed) {
        var random=new System.Random(seed);var texture=new Texture2D(128,128,TextureFormat.RGB24,false);
        for(int y=0;y<128;y++) for(int x=0;x<128;x++) {
            // Unique printed wall patterns make image-feature repeatability measurable.
            float v=(float)random.NextDouble();
            texture.SetPixel(x,y,new Color(v,Mathf.Clamp01(v*.8f+.08f),Mathf.Clamp01(v*.7f+.18f)));
        }
        texture.Apply();texture.filterMode=FilterMode.Bilinear;
        var m=Surface(Color.white);m.mainTexture=texture;return m;
    }
    public static void Run() {
        var input=Path.Combine(Application.streamingAssetsPath,"research-scene.json");
        var spec=JsonUtility.FromJson<ResearchScene>(File.ReadAllText(input));
        Directory.CreateDirectory(spec.output);
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        RenderSettings.ambientLight=new Color(.8f,.8f,.8f);
        RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;
        var light=new GameObject("Soft directional light").AddComponent<Light>();
        light.type=LightType.Directional;light.intensity=.65f;light.transform.rotation=Quaternion.Euler(55,35,0);
        var floor=Surface(new Color(.72f,.75f,.76f));
        var occupied=new HashSet<string>();
        foreach(var cell in spec.cells)occupied.Add(cell.level+":"+cell.x+":"+cell.z);
        int serial=0;
        foreach(var c in spec.cells) {
            Box("Floor "+c.level,new Vector3(c.x*.5f,c.y-.06f,-c.z*.5f),new Vector3(.5f,.12f,.5f),floor);
            int[,] dirs={{1,0},{-1,0},{0,1},{0,-1}};
            for(int d=0;d<4;d++) {
                int dx=dirs[d,0],dz=dirs[d,1];
                if(occupied.Contains(c.level+":"+(c.x+dx)+":"+(c.z+dz)))continue;
                var material=Pattern(++serial*97);
                Box("Wall "+c.level,new Vector3(c.x*.5f+dx*.25f,c.y+1.5f,-c.z*.5f-dz*.25f),
                    new Vector3(dx!=0?.08f:.5f,3f,dz!=0?.08f:.5f),material);
            }
        }
        foreach(var node in spec.nodes) {
            if(!node.id.StartsWith("e1_")&&!node.id.StartsWith("e2_"))continue;
            var p=ToUnity(node.position);
            Box("Elevator landing "+node.id,p+new Vector3(0,.02f,0),new Vector3(1.2f,.04f,1.2f),Surface(new Color(.12f,.53f,.65f)));
        }
        var camera=new GameObject("Research camera").AddComponent<Camera>();
        camera.fieldOfView=spec.vertical_fov;camera.aspect=(float)spec.width/spec.height;
        camera.nearClipPlane=.05f;camera.farClipPlane=80f;camera.clearFlags=CameraClearFlags.SolidColor;
        camera.backgroundColor=new Color(.06f,.09f,.12f);
        camera.allowHDR=false;camera.allowMSAA=false;
        var target=new RenderTexture(spec.width,spec.height,24,RenderTextureFormat.ARGB32,RenderTextureReadWrite.Linear);
        camera.targetTexture=target;var records=new List<ViewRecord>();
        Physics.SyncTransforms();
        foreach(var capture in spec.captures) {
            camera.transform.position=ToUnity(capture.position);
            // Yaw is Unity-world yaw; export actual pose rather than assuming handedness.
            camera.transform.rotation=Quaternion.Euler(0,capture.yaw,0);
            camera.Render();RenderTexture.active=target;
            var texture=new Texture2D(spec.width,spec.height,TextureFormat.RGB24,false,true);
            texture.ReadPixels(new Rect(0,0,spec.width,spec.height),0,0);texture.Apply();
            string image=capture.id+".png";File.WriteAllBytes(Path.Combine(spec.output,image),texture.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(texture);
            string depth=null;
            if(capture.split=="mapping") {
                depth=capture.id+".depth";
                using(var writer=new BinaryWriter(File.Open(Path.Combine(spec.output,depth),FileMode.Create))) {
                    for(int y=0;y<spec.height;y++)for(int x=0;x<spec.width;x++) {
                        Ray ray=camera.ScreenPointToRay(new Vector3(x+.5f,spec.height-y-.5f,0));
                        float z=0;
                        if(Physics.Raycast(ray,out var hit,80f)) z=Vector3.Dot(hit.point-camera.transform.position,camera.transform.forward);
                        writer.Write(z);
                    }
                }
            }
            // C_cv=(x,-y,z) in Unity camera coordinates, W_internal=(x,y,-z) in Unity world.
            var transform=camera.transform.localToWorldMatrix;
            float[] pose=new float[16];float[] ws={1,1,-1,1},cs={1,-1,1,1};
            for(int r=0;r<4;r++)for(int c=0;c<4;c++)pose[r*4+c]=ws[r]*transform[r,c]*cs[c];
            float f=spec.height/(2*Mathf.Tan(spec.vertical_fov*Mathf.Deg2Rad/2));
            records.Add(new ViewRecord {id=capture.id,split=capture.split,floor=capture.floor,image=image,depth=depth,
                camera_to_world=pose,width=spec.width,height=spec.height,fx=f,fy=f,cx=(spec.width-1)/2f,cy=(spec.height-1)/2f});
            Debug.Log("RESEARCH_CAPTURE "+capture.id);
        }
        File.WriteAllText(Path.Combine(spec.output,"capture-manifest.json"),JsonUtility.ToJson(new CaptureManifest {scene_revision=spec.scene_revision,records=records.ToArray()},true));
        EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(),"Assets/ResearchStation.unity");
        RenderTexture.active=null;target.Release();
        Debug.Log("RESEARCH_COMPLETE "+records.Count);
    }
}
