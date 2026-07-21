using System.IO;
using TMPro;
using UdonSharp;
using UdonSharpEditor;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;
using VRC.SDKBase;
using VRC.Udon;

public static class AddProximityDialogToScene
{
    private const string ModuleRoot = "Assets/ConvenienceStoreDialog";
    private const string ScenePath = "Assets/Scenes/VRCDefaultWorldScene.unity";
    private const string RootName = "NPC_DialogTrigger_Demo";
    private const string RequestPath = "Temp/AddProximityDialogToScene.request";
    private const string DialogScriptPath = ModuleRoot + "/Runtime/ProximityDialogTrigger.cs";
    private const string DialogAssetPath = ModuleRoot + "/Runtime/ProximityDialogTrigger.asset";
    private const string ChoiceButtonScriptPath = ModuleRoot + "/Runtime/ProximityDialogChoiceButton.cs";
    private const string ChoiceButtonAssetPath = ModuleRoot + "/Runtime/ProximityDialogChoiceButton.asset";
    private const string VoiceReceiverScriptPath = ModuleRoot + "/Runtime/VoiceChoiceReceiver.cs";
    private const string VoiceReceiverAssetPath = ModuleRoot + "/Runtime/VoiceChoiceReceiver.asset";
    private const string JapaneseFontPath = ModuleRoot + "/Fonts/NotoSansCJKjp-Regular.otf";
    private const string JapaneseTMPFontPath = ModuleRoot + "/Fonts/NotoSansCJKjp-Regular SDF.asset";
    private const string DefaultVoicePollUrl = "http://127.0.0.1:8765/session/default/latest";

    [InitializeOnLoadMethod]
    private static void AutoRunIfRequested()
    {
        EditorApplication.delayCall += TryAutoRunIfRequested;
    }

    [MenuItem("Tools/Convenience Store Dialog/Install Or Refresh In Current Scene")]
    public static void AddToCurrentSceneFromMenu()
    {
        AddToScene(EditorSceneManager.GetActiveScene().path);
    }

    public static void AddToVRCDefaultWorldScene()
    {
        AddToScene(ScenePath);
    }

    private static void TryAutoRunIfRequested()
    {
        if (!File.Exists(RequestPath))
        {
            return;
        }

        if (EditorApplication.isPlayingOrWillChangePlaymode)
        {
            EditorApplication.isPlaying = false;
            EditorApplication.delayCall += TryAutoRunIfRequested;
            return;
        }

        File.Delete(RequestPath);
        AddToScene(ScenePath);
        Debug.Log("Added or updated NPC_DialogTrigger_Demo clickable dialog object.");
    }

    private static void AddToScene(string scenePath)
    {
        if (string.IsNullOrEmpty(scenePath))
        {
            scenePath = ScenePath;
        }

        if (EditorSceneManager.GetActiveScene().path != scenePath)
        {
            EditorSceneManager.OpenScene(scenePath);
        }

        var root = GameObject.Find(RootName);
        if (root == null)
        {
            root = new GameObject(RootName);
            root.transform.position = GetPlacementPosition();
        }

        var oldTrigger = root.GetComponent<SphereCollider>();
        if (oldTrigger != null)
        {
            Object.DestroyImmediate(oldTrigger);
        }

        EnsureProgramAsset(DialogScriptPath, DialogAssetPath);
        EnsureProgramAsset(ChoiceButtonScriptPath, ChoiceButtonAssetPath);
        EnsureProgramAsset(VoiceReceiverScriptPath, VoiceReceiverAssetPath);
        var japaneseFont = EnsureJapaneseFontAsset();

        var dialog = RecreateDialogComponent(root);
        var voiceReceiver = RecreateVoiceReceiverComponent(root);

        var marker = BuildMarker(root.transform);
        marker.transform.localPosition = new Vector3(0f, 0.9f, 0f);
        marker.transform.localScale = new Vector3(0.6f, 0.9f, 0.6f);

        var canvasObject = FindOrCreateChild(root.transform, "Dialog_Canvas");
        canvasObject.transform.localPosition = new Vector3(0f, 2.45f, 0f);
        canvasObject.transform.localRotation = Quaternion.identity;
        canvasObject.SetActive(true);

        var canvas = GetOrAdd<Canvas>(canvasObject);
        canvas.renderMode = RenderMode.WorldSpace;
        canvas.sortingOrder = 10;
        GetOrAdd<CanvasScaler>(canvasObject).dynamicPixelsPerUnit = 10f;
        GetOrAdd<GraphicRaycaster>(canvasObject);

        var canvasRect = GetOrAdd<RectTransform>(canvasObject);
        canvasRect.sizeDelta = new Vector2(560f, 340f);
        canvasRect.localScale = new Vector3(0.01f, 0.01f, 0.01f);

        BuildPanel(canvasObject.transform);
        var dialogText = BuildText(canvasObject.transform, "Dialog_Text", new Vector2(0f, 0.49f), Vector2.one, new Vector2(28f, 4f), new Vector2(-28f, -20f), 24f, TextAlignmentOptions.Center, Color.white, japaneseFont);
        var statusText = BuildText(canvasObject.transform, "Status_Text", new Vector2(0f, 0.39f), new Vector2(1f, 0.49f), new Vector2(28f, 0f), new Vector2(-28f, 0f), 15f, TextAlignmentOptions.Center, new Color(1f, 1f, 1f, 0.76f), japaneseFont);
        dialogText.text = "店員：いらっしゃいませ。\n今日は何をお探しですか？";
        statusText.text = "返信をクリックして選んでください";

        DestroyChildIfExists(canvasObject.transform, "Player_InputField");
        DestroyChildIfExists(canvasObject.transform, "Input_Hint");
        DestroyChildIfExists(canvasObject.transform, "Mode_Hint");

        var choice0 = BuildChoiceButton(canvasObject.transform, "Choice_0_Button", 0, new Vector2(0f, 0.27f), new Vector2(1f, 0.38f), "1. 唐揚げ弁当を探しています", japaneseFont, dialog);
        var choice1 = BuildChoiceButton(canvasObject.transform, "Choice_1_Button", 1, new Vector2(0f, 0.15f), new Vector2(1f, 0.26f), "2. コーヒーはありますか？", japaneseFont, dialog);
        var choice2 = BuildChoiceButton(canvasObject.transform, "Choice_2_Button", 2, new Vector2(0f, 0.03f), new Vector2(1f, 0.14f), "3. ATM はどこですか？", japaneseFont, dialog);

        dialog.dialogRoot = canvasObject;
        dialog.dialogText = dialogText;
        dialog.statusText = statusText;
        dialog.choice0Root = choice0.root;
        dialog.choice1Root = choice1.root;
        dialog.choice2Root = choice2.root;
        dialog.choice0Text = choice0.text;
        dialog.choice1Text = choice1.text;
        dialog.choice2Text = choice2.text;
        dialog.dialogTransform = canvasObject.transform;
        dialog.triggerDistance = 3.25f;

        voiceReceiver.dialog = dialog;
        voiceReceiver.statusText = statusText;
        voiceReceiver.pollUrl = new VRCUrl(DefaultVoicePollUrl);
        voiceReceiver.pollIntervalSeconds = 1f;
        voiceReceiver.enablePolling = true;

        EditorUtility.SetDirty(root);
        EditorUtility.SetDirty(dialog);
        EditorUtility.SetDirty(voiceReceiver);
        UdonSharpProgramAsset.CompileAllCsPrograms(true);
        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
        EditorSceneManager.SaveOpenScenes();
        AssetDatabase.SaveAssets();
    }

    private static GameObject BuildMarker(Transform parent)
    {
        var marker = FindOrCreateChild(parent, "Visible_NPC_Marker");
        if (marker.GetComponent<MeshFilter>() == null)
        {
            Object.DestroyImmediate(marker);
            marker = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            marker.name = "Visible_NPC_Marker";
            marker.transform.SetParent(parent, false);
            Object.DestroyImmediate(marker.GetComponent<Collider>());
        }

        ApplyMaterial(marker, new Color(0.1f, 0.75f, 1f, 1f));
        return marker;
    }

    private static void BuildPanel(Transform parent)
    {
        var panelObject = FindOrCreateChild(parent, "Dialog_Background");
        var panelRect = GetOrAdd<RectTransform>(panelObject);
        panelRect.anchorMin = Vector2.zero;
        panelRect.anchorMax = Vector2.one;
        panelRect.offsetMin = Vector2.zero;
        panelRect.offsetMax = Vector2.zero;
        var image = GetOrAdd<Image>(panelObject);
        image.color = new Color(0.02f, 0.03f, 0.05f, 0.9f);
    }

    private static TextMeshProUGUI BuildText(Transform parent, string name, Vector2 anchorMin, Vector2 anchorMax, Vector2 offsetMin, Vector2 offsetMax, float fontSize, TextAlignmentOptions alignment, Color color, TMP_FontAsset font)
    {
        var textObject = FindOrCreateChild(parent, name);
        var textRect = GetOrAdd<RectTransform>(textObject);
        textRect.anchorMin = anchorMin;
        textRect.anchorMax = anchorMax;
        textRect.offsetMin = offsetMin;
        textRect.offsetMax = offsetMax;

        var text = GetOrAdd<TextMeshProUGUI>(textObject);
        text.enabled = true;
        text.font = font;
        text.fontSize = fontSize;
        text.alignment = alignment;
        text.color = color;
        text.enableWordWrapping = true;
        text.raycastTarget = false;
        return text;
    }

    private static ChoiceButtonParts BuildChoiceButton(Transform parent, string name, int index, Vector2 anchorMin, Vector2 anchorMax, string label, TMP_FontAsset font, ProximityDialogTrigger dialog)
    {
        var buttonObject = FindOrCreateChild(parent, name);
        var buttonRect = GetOrAdd<RectTransform>(buttonObject);
        buttonRect.anchorMin = anchorMin;
        buttonRect.anchorMax = anchorMax;
        buttonRect.offsetMin = new Vector2(28f, 0f);
        buttonRect.offsetMax = new Vector2(-28f, 0f);

        var image = GetOrAdd<Image>(buttonObject);
        image.color = new Color(0.07f, 0.24f, 0.31f, 0.96f);
        image.raycastTarget = false;

        var collider = GetOrAdd<BoxCollider>(buttonObject);
        collider.isTrigger = false;
        collider.center = Vector3.zero;
        collider.size = new Vector3(504f, 34f, 4f);

        var textObject = FindOrCreateChild(buttonObject.transform, "Label");
        var textRect = GetOrAdd<RectTransform>(textObject);
        textRect.anchorMin = Vector2.zero;
        textRect.anchorMax = Vector2.one;
        textRect.offsetMin = new Vector2(16f, 0f);
        textRect.offsetMax = new Vector2(-16f, 0f);

        var text = GetOrAdd<TextMeshProUGUI>(textObject);
        text.text = label;
        text.font = font;
        text.fontSize = 17f;
        text.alignment = TextAlignmentOptions.MidlineLeft;
        text.color = Color.white;
        text.enableWordWrapping = false;
        text.raycastTarget = false;

        var button = RecreateChoiceButtonComponent(buttonObject);
        button.dialog = dialog;
        button.choiceIndex = index;
        SetInteractionPrompt(UdonSharpEditorUtility.GetBackingUdonBehaviour(button), "\u9078\u629e", 4f);
        EditorUtility.SetDirty(button);

        return new ChoiceButtonParts { root = buttonObject, text = text };
    }

    private static TMP_FontAsset EnsureJapaneseFontAsset()
    {
        var existing = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(JapaneseTMPFontPath);
        if (IsUsableFontAsset(existing))
        {
            return existing;
        }

        if (existing != null)
        {
            AssetDatabase.DeleteAsset(JapaneseTMPFontPath);
        }

        AssetDatabase.ImportAsset(JapaneseFontPath, ImportAssetOptions.ForceSynchronousImport);
        var sourceFont = AssetDatabase.LoadAssetAtPath<Font>(JapaneseFontPath);
        if (sourceFont == null)
        {
            throw new FileNotFoundException("Could not load Japanese font", JapaneseFontPath);
        }

        var fontAsset = TMP_FontAsset.CreateFontAsset(
            sourceFont,
            90,
            9,
            UnityEngine.TextCore.LowLevel.GlyphRenderMode.SDFAA,
            4096,
            4096,
            AtlasPopulationMode.Dynamic);

        fontAsset.name = "NotoSansCJKjp-Regular SDF";
        EnsureFontAtlasObjects(fontAsset);
        AssetDatabase.CreateAsset(fontAsset, JapaneseTMPFontPath);
        AssetDatabase.AddObjectToAsset(fontAsset.atlasTextures[0], fontAsset);
        AssetDatabase.AddObjectToAsset(fontAsset.material, fontAsset);
        AssetDatabase.SaveAssets();
        AssetDatabase.ImportAsset(JapaneseTMPFontPath, ImportAssetOptions.ForceSynchronousImport);

        var reloaded = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(JapaneseTMPFontPath);
        if (!IsUsableFontAsset(reloaded))
        {
            throw new FileNotFoundException("Could not create usable Japanese TMP font asset", JapaneseTMPFontPath);
        }

        return reloaded;
    }

    private static bool IsUsableFontAsset(TMP_FontAsset fontAsset)
    {
        return fontAsset != null
            && fontAsset.atlasTextures != null
            && fontAsset.atlasTextures.Length > 0
            && fontAsset.atlasTextures[0] != null
            && fontAsset.material != null;
    }

    private static void EnsureFontAtlasObjects(TMP_FontAsset fontAsset)
    {
        if (fontAsset.atlasTextures == null || fontAsset.atlasTextures.Length == 0 || fontAsset.atlasTextures[0] == null)
        {
            var atlas = new Texture2D(4096, 4096, TextureFormat.Alpha8, false)
            {
                name = "NotoSansCJKjp-Regular SDF Atlas"
            };
            fontAsset.atlasTextures = new[] { atlas };
        }

        if (fontAsset.material == null)
        {
            var shader = Shader.Find("TextMeshPro/Distance Field");
            var material = new Material(shader)
            {
                name = "NotoSansCJKjp-Regular SDF Material"
            };
            material.SetTexture("_MainTex", fontAsset.atlasTextures[0]);
            fontAsset.material = material;
        }
    }

    private static void EnsureProgramAsset(string scriptPath, string assetPath)
    {
        var programAsset = AssetDatabase.LoadAssetAtPath<UdonSharpProgramAsset>(assetPath);
        var script = AssetDatabase.LoadAssetAtPath<MonoScript>(scriptPath);

        if (script == null)
        {
            throw new FileNotFoundException("Could not find UdonSharp script", scriptPath);
        }

        if (programAsset == null)
        {
            programAsset = ScriptableObject.CreateInstance<UdonSharpProgramAsset>();
            programAsset.sourceCsScript = script;
            AssetDatabase.CreateAsset(programAsset, assetPath);
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceSynchronousImport);
            AssetDatabase.Refresh();
        }
        else if (programAsset.sourceCsScript != script)
        {
            programAsset.sourceCsScript = script;
            EditorUtility.SetDirty(programAsset);
        }
    }

    private static ProximityDialogTrigger RecreateDialogComponent(GameObject root)
    {
        var existing = root.GetComponent<ProximityDialogTrigger>();
        if (existing != null)
        {
            var backingBehaviour = UdonSharpEditorUtility.GetBackingUdonBehaviour(existing);
            Object.DestroyImmediate(existing);

            if (backingBehaviour != null)
            {
                Object.DestroyImmediate(backingBehaviour);
            }
        }

        foreach (var orphan in root.GetComponents<UdonBehaviour>())
        {
            if (orphan.programSource == null || orphan.programSource.name == "ProximityDialogTrigger")
            {
                Object.DestroyImmediate(orphan);
            }
        }

        return root.AddUdonSharpComponent<ProximityDialogTrigger>();
    }

    private static ProximityDialogChoiceButton RecreateChoiceButtonComponent(GameObject target)
    {
        var existing = target.GetComponent<ProximityDialogChoiceButton>();
        if (existing != null)
        {
            var backingBehaviour = UdonSharpEditorUtility.GetBackingUdonBehaviour(existing);
            Object.DestroyImmediate(existing);

            if (backingBehaviour != null)
            {
                Object.DestroyImmediate(backingBehaviour);
            }
        }

        foreach (var orphan in target.GetComponents<UdonBehaviour>())
        {
            if (orphan.programSource == null || orphan.programSource.name == "ProximityDialogChoiceButton")
            {
                Object.DestroyImmediate(orphan);
            }
        }

        return target.AddUdonSharpComponent<ProximityDialogChoiceButton>();
    }

    private static VoiceChoiceReceiver RecreateVoiceReceiverComponent(GameObject root)
    {
        var existing = root.GetComponent<VoiceChoiceReceiver>();
        if (existing != null)
        {
            var backingBehaviour = UdonSharpEditorUtility.GetBackingUdonBehaviour(existing);
            Object.DestroyImmediate(existing);

            if (backingBehaviour != null)
            {
                Object.DestroyImmediate(backingBehaviour);
            }
        }

        foreach (var orphan in root.GetComponents<UdonBehaviour>())
        {
            if (orphan.programSource == null || orphan.programSource.name == "VoiceChoiceReceiver")
            {
                Object.DestroyImmediate(orphan);
            }
        }

        return root.AddUdonSharpComponent<VoiceChoiceReceiver>();
    }

    private static void SetInteractionPrompt(UdonBehaviour behaviour, string text, float proximity)
    {
        if (behaviour == null)
        {
            return;
        }

        var serialized = new SerializedObject(behaviour);
        var textProperty = serialized.FindProperty("interactText");
        if (textProperty != null)
        {
            textProperty.stringValue = text;
        }

        var proximityProperty = serialized.FindProperty("proximity");
        if (proximityProperty != null)
        {
            proximityProperty.floatValue = proximity;
        }

        serialized.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(behaviour);
    }

    private static Vector3 GetPlacementPosition()
    {
        var vrcWorld = GameObject.Find("VRCWorld");
        if (vrcWorld != null)
        {
            return vrcWorld.transform.position + new Vector3(0f, 1f, 3f);
        }

        var camera = Camera.main;
        if (camera != null)
        {
            return camera.transform.position + camera.transform.forward * 3f;
        }

        return new Vector3(-30f, 57f, 63f);
    }

    private static GameObject FindOrCreateChild(Transform parent, string childName)
    {
        var child = parent.Find(childName);
        if (child != null)
        {
            return child.gameObject;
        }

        var gameObject = new GameObject(childName);
        gameObject.transform.SetParent(parent, false);
        return gameObject;
    }

    private static void DestroyChildIfExists(Transform parent, string childName)
    {
        var child = parent.Find(childName);
        if (child != null)
        {
            Object.DestroyImmediate(child.gameObject);
        }
    }

    private static T GetOrAdd<T>(GameObject gameObject) where T : Component
    {
        var component = gameObject.GetComponent<T>();
        if (component != null)
        {
            return component;
        }

        return gameObject.AddComponent<T>();
    }

    private static void ApplyMaterial(GameObject target, Color color)
    {
        var renderer = target.GetComponent<Renderer>();
        if (renderer == null)
        {
            return;
        }

        var material = new Material(Shader.Find("Standard"))
        {
            name = "NPC_DialogMarker_Material",
            color = color
        };
        renderer.sharedMaterial = material;
    }

    private struct ChoiceButtonParts
    {
        public GameObject root;
        public TextMeshProUGUI text;
    }
}
