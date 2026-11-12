using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;

[Serializable] public class VCell {public int x,z;public float y;public string level;}
[Serializable] public class VView {public string id,split;public float[] position;public float yaw,pitch;}
[Serializable] public class VSpec {public VCell[] cells;public VView[] mapping;public string output;public int width,height;public float fov;}

// The same geometry generator builds the offline map and the XR Simulation environment.
// Texture identity is a synthetic experimental aid, not a real-station appearance model.
public class VisualStationEnvironment:MonoBehaviour {
    public string specificationJson;
    public bool repeated;
    GameObject content;
    List<Renderer> walls=new List<Renderer>();
    List<Material> originals=new List<Material>();
    static Material Plain(Color c){var m=new Material(Shader.Find("Unlit/Color"));m.color=c;return m;}
    static Material Pattern(int seed) {
        var random=new System.Random(seed);var pixels=new Color[128*128];
        // Printed pattern panels, deliberately distinguishable in the nominal condition.
        for(int i=0;i<pixels.Length;i++){float v=(float)random.NextDouble();pixels[i]=new Color(v,v*.8f+.08f,v*.7f+.18f);}
        var t=new Texture2D(128,128,TextureFormat.RGB24,false);t.SetPixels(pixels);t.Apply();t.filterMode=FilterMode.Bilinear;
        var m=new Material(Shader.Find("Unlit/Texture"));m.mainTexture=t;return m;
    }
    GameObject Box(string name,Vector3 p,Vector3 scale,Material m){
        var g=GameObject.CreatePrimitive(PrimitiveType.Cube);g.name=name;g.transform.SetParent(content.transform);
        g.transform.position=p;g.transform.localScale=scale;g.GetComponent<Renderer>().sharedMaterial=m;return g;
    }
    void OnEnable(){if(Application.isPlaying)Build();}
    public void Build(){
        if(content!=null)return;
        var spec=JsonUtility.FromJson<VSpec>(specificationJson);content=new GameObject("Generated visual station");content.transform.SetParent(transform);
        var floor=Plain(new Color(.72f,.75f,.76f));var occupied=new HashSet<string>();
        foreach(var c in spec.cells)occupied.Add(c.level+":"+c.x+":"+c.z);
        int serial=0;int[,] dirs={{1,0},{-1,0},{0,1},{0,-1}};
        foreach(var c in spec.cells){
            Box("Floor "+c.level,new Vector3(c.x*.5f,c.y-.06f,-c.z*.5f),new Vector3(.5f,.12f,.5f),floor);
            for(int d=0;d<4;d++){
                int dx=dirs[d,0],dz=dirs[d,1];if(occupied.Contains(c.level+":"+(c.x+dx)+":"+(c.z+dz)))continue;
                var m=Pattern(++serial*97);
                var g=Box("Visual wall "+serial,new Vector3(c.x*.5f+dx*.25f,c.y+1.5f,-c.z*.5f-dz*.25f),new Vector3(dx!=0?.08f:.5f,3f,dz!=0?.08f:.5f),m);
                walls.Add(g.GetComponent<Renderer>());originals.Add(m);
            }
        }
        SetRepeated(repeated);
    }
    public void SetRepeated(bool value){repeated=value;for(int i=0;i<walls.Count;i++)walls[i].sharedMaterial=originals[value?i%4:i];}
}
