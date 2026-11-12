using System;
using System.IO;
using UnityEngine;

[Serializable] public class WalkPoint { public float[] position; }
[Serializable] public class WalkSpec {
    public string revision, output; public float length, fov, corridor_half_width, ceiling_height;
    public int width, height; public WalkPoint[] path; public VView[] mapping;
}

// Dimensions and assets are authored for the experiment, not surveyed Gangnam geometry.
public class GangnamWalkEnvironment : MonoBehaviour {
    public string specificationJson;
    GameObject content;
    Material ColorMat(string hex) {
        ColorUtility.TryParseHtmlString(hex, out var c);
        var m=new Material(Shader.Find("Unlit/Color")); m.color=c; return m;
    }
    GameObject Box(string name,Vector3 p,Vector3 size,Material m) {
        var g=GameObject.CreatePrimitive(PrimitiveType.Cube);g.name=name;g.transform.SetParent(content.transform);
        g.transform.position=p;g.transform.localScale=size;g.GetComponent<Renderer>().sharedMaterial=m;return g;
    }
    void Panel(string file,Vector3 p,Vector2 size,float yaw) {
        var texture=new Texture2D(2,2,TextureFormat.RGB24,false);
        texture.LoadImage(File.ReadAllBytes(Path.Combine(Application.streamingAssetsPath,"GangnamWalk",file+".png")));
        texture.filterMode=FilterMode.Bilinear;
        var m=new Material(Shader.Find("Unlit/Texture"));m.mainTexture=texture;
        var g=GameObject.CreatePrimitive(PrimitiveType.Quad);g.name=file;g.transform.SetParent(content.transform);
        g.transform.position=p;g.transform.rotation=Quaternion.Euler(0,yaw,0);g.transform.localScale=new Vector3(size.x,size.y,1);
        g.GetComponent<Renderer>().sharedMaterial=m;
    }
    void OnEnable(){if(Application.isPlaying)Build();}
    public void Build() {
        if(content!=null)return;
        var s=JsonUtility.FromJson<WalkSpec>(specificationJson);
        content=new GameObject("Authored synthetic approach");content.transform.SetParent(transform);
        var wall=ColorMat("#DADCD7");var trim=ColorMat("#A9B1AA");var dark=ColorMat("#26443F");
        var floor=ColorMat("#B6BAB5");var alternate=ColorMat("#BFC2BC");var seam=ColorMat("#929B94");
        var metal=ColorMat("#889A99");var silver=ColorMat("#B8C5C1");var lamp=ColorMat("#F2F4E5");
        float end=s.length+1.3f,w=s.corridor_half_width,h=s.ceiling_height;
        Box("Underfloor",new Vector3(0,-.09f,-end/2),new Vector3(w*2,.16f,end+6),seam);
        for(int z=-3;z<Mathf.CeilToInt(end);z++)for(int x=-3;x<4;x++)
            Box("Floor tile",new Vector3(x,-.012f,-z-.5f),new Vector3(.985f,.02f,.985f),(x+z)%2==0?floor:alternate);
        for(int side=-1;side<=1;side+=2) {
            Box("Side wall",new Vector3(side*w,h/2,-end/2),new Vector3(.14f,h,end+6),wall);
            Box("Wall base",new Vector3(side*(w-.08f),.14f,-end/2),new Vector3(.06f,.28f,end+6),trim);
            Box("Wayfinding band",new Vector3(side*(w-.08f),2.72f,-end/2),new Vector3(.06f,.17f,end+6),dark);
            for(int i=0;i<9;i++) {
                float z=1.0f+i*2.5f;
                Panel("poster-"+(i+(side>0?9:0)).ToString("D2"),new Vector3(side*(w-.09f),1.67f,-z),new Vector2(1.05f,1.31f),side<0?-90:90);
                Box("Poster rail",new Vector3(side*(w-.08f),.94f,-z),new Vector3(.06f,.035f,1.18f),metal);
            }
            for(int i=0;i<5;i++)Box("Column",new Vector3(side*(w-.22f),h/2,-2.4f-i*5),new Vector3(.45f,h,.4f),trim);
        }
        Box("Ceiling",new Vector3(0,h+.06f,-end/2),new Vector3(w*2,.1f,end+6),wall);
        for(int z=0;z<end;z+=3)for(int side=-1;side<=1;side+=2)
            Box("Ceiling light",new Vector3(side*1.4f,h-.02f,-z),new Vector3(.18f,.05f,1.8f),lamp);
        Box("End wall",new Vector3(0,h/2,-end-.05f),new Vector3(w*2,h,.1f),wall);
        Box("Lift frame",new Vector3(0,1.19f,-end+.04f),new Vector3(2.4f,2.38f,.16f),dark);
        Box("Lift left door",new Vector3(-.55f,1.14f,-end+.14f),new Vector3(1.08f,2.25f,.1f),silver);
        Box("Lift right door",new Vector3(.55f,1.14f,-end+.14f),new Vector3(1.08f,2.25f,.1f),metal);
        Box("Call panel",new Vector3(1.42f,1.05f,-end+.13f),new Vector3(.18f,.42f,.08f),metal);
        Box("Call button",new Vector3(1.42f,1.1f,-end+.18f),new Vector3(.06f,.06f,.02f),lamp);
        Panel("elevator",new Vector3(0,2.8f,-end+.17f),new Vector2(3.0f,.75f),180);
        Panel("lift-info",new Vector3(-1.9f,1.55f,-end+.17f),new Vector2(.95f,1.19f),180);
        Panel("poster-06",new Vector3(2.25f,1.55f,-end+.17f),new Vector2(1.05f,1.31f),180);
        Panel("lift-info",new Vector3(.55f,1.45f,-end+.201f),new Vector2(.48f,.6f),180);
        for(int z=5;z<end-3;z+=9) {
            Box("Suspended sign",new Vector3(0,2.8f,-z-.03f),new Vector3(2.5f,.625f,.08f),dark);
            Panel("wayfinding",new Vector3(0,2.8f,-z+.02f),new Vector2(2.5f,.625f),180);
        }
    }
}
