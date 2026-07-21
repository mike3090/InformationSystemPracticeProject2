using TMPro;
using UdonSharp;
using UnityEngine;
using VRC.SDKBase;

public class ProximityDialogTrigger : UdonSharpBehaviour
{
    public GameObject dialogRoot;
    public TextMeshProUGUI dialogText;
    public TextMeshProUGUI statusText;
    public GameObject choice0Root;
    public GameObject choice1Root;
    public GameObject choice2Root;
    public TextMeshProUGUI choice0Text;
    public TextMeshProUGUI choice1Text;
    public TextMeshProUGUI choice2Text;
    public Transform dialogTransform;

    public float triggerDistance = 3.25f;

    private VRCPlayerApi _localPlayer;
    private bool _isNear;
    private int _step;

    private void Start()
    {
        _localPlayer = Networking.LocalPlayer;
        SetDialogVisible(false);
    }

    public override void OnPlayerTriggerEnter(VRCPlayerApi player)
    {
        if (player == null || !player.isLocal)
        {
            return;
        }

        EnterDialogRange();
    }

    public override void OnPlayerTriggerExit(VRCPlayerApi player)
    {
        if (player == null || !player.isLocal)
        {
            return;
        }

        ExitDialogRange();
    }

    public void SelectChoice0()
    {
        SelectChoice(0);
    }

    public void SelectChoice1()
    {
        SelectChoice(1);
    }

    public void SelectChoice2()
    {
        SelectChoice(2);
    }

    private void Update()
    {
        if (_localPlayer == null)
        {
            _localPlayer = Networking.LocalPlayer;
            return;
        }

        var distance = Vector3.Distance(_localPlayer.GetPosition(), transform.position);
        var shouldBeNear = distance <= triggerDistance;

        if (shouldBeNear && !_isNear)
        {
            EnterDialogRange();
        }
        else if (!shouldBeNear && _isNear)
        {
            ExitDialogRange();
        }

        FaceLocalPlayer();
    }

    private void EnterDialogRange()
    {
        _isNear = true;
        _step = 0;
        SetDialogVisible(true);
        RefreshDialog();
    }

    private void ExitDialogRange()
    {
        _isNear = false;
        SetDialogVisible(false);
    }

    private void SelectChoice(int choiceIndex)
    {
        if (!_isNear)
        {
            return;
        }

        if (_step == 0)
        {
            if (choiceIndex == 0)
            {
                _step = 1;
            }
            else if (choiceIndex == 1)
            {
                _step = 5;
            }
            else
            {
                _step = 6;
            }
        }
        else if (_step == 1)
        {
            _step = 2;
        }
        else if (_step == 2)
        {
            _step = 3;
        }
        else if (_step == 3)
        {
            _step = 4;
        }
        else if (_step == 4)
        {
            if (choiceIndex == 0)
            {
                _step = 0;
            }
            else if (choiceIndex == 1)
            {
                _step = 0;
            }
            else
            {
                _step = 7;
            }
        }
        else if (_step == 5)
        {
            if (choiceIndex == 0)
            {
                _step = 1;
            }
            else if (choiceIndex == 1)
            {
                _step = 4;
            }
            else
            {
                _step = 0;
            }
        }
        else if (_step == 6)
        {
            if (choiceIndex == 0)
            {
                _step = 1;
            }
            else if (choiceIndex == 1)
            {
                _step = 5;
            }
            else
            {
                _step = 4;
            }
        }
        else
        {
            _step = 0;
        }

        RefreshDialog();
    }

    private void RefreshDialog()
    {
        if (_step == 0)
        {
            SetDialogText("店員：いらっしゃいませ。\n今日は何をお探しですか？");
            SetChoices(
                "1. 唐揚げ弁当を探しています",
                "2. コーヒーはありますか？",
                "3. ATM はどこですか？");
        }
        else if (_step == 1)
        {
            SetDialogText("店員：唐揚げ弁当ですね。\nお弁当は奥の冷蔵棚にあります。\nレジで温めますか？");
            SetChoices(
                "1. 温めてください",
                "2. そのままで大丈夫です",
                "3. 袋もお願いします");
        }
        else if (_step == 2)
        {
            SetDialogText("店員：かしこまりました。\n袋はご利用ですか？");
            SetChoices(
                "1. 袋はいりません",
                "2. 袋をお願いします",
                "3. 箸をください");
        }
        else if (_step == 3)
        {
            SetDialogText("店員：お箸をお付けします。\nお支払いはどうされますか？");
            SetChoices(
                "1. Suicaでお願いします",
                "2. 現金でお願いします",
                "3. クレジットカードでお願いします");
        }
        else if (_step == 4)
        {
            SetDialogText("店員：ありがとうございます。\nお会計は五百八十円です。\nまたお越しくださいませ。");
            SetChoices(
                "1. もう一度練習する",
                "2. 他の商品を聞く",
                "3. 終了する");
        }
        else if (_step == 5)
        {
            SetDialogText("店員：コーヒーですね。\nホットはレジ横、アイスは冷蔵ケースにあります。");
            SetChoices(
                "1. 弁当も探しています",
                "2. ありがとうございます",
                "3. 最初に戻る");
        }
        else if (_step == 6)
        {
            SetDialogText("店員：ATM は入口の右側にあります。\nほかにお探しのものはありますか？");
            SetChoices(
                "1. 弁当を探しています",
                "2. コーヒーを買いたいです",
                "3. ありません");
        }
        else
        {
            SetDialogText("店員：ご利用ありがとうございました。\nまたお越しくださいませ。");
            SetChoices("1. もう一度練習する", "", "");
        }

        if (statusText != null)
        {
            statusText.text = "返信をクリックして選んでください";
        }
    }

    private void SetDialogText(string text)
    {
        if (dialogText != null)
        {
            dialogText.text = text;
        }
    }

    private void SetChoices(string choice0, string choice1, string choice2)
    {
        SetChoice(choice0Root, choice0Text, choice0);
        SetChoice(choice1Root, choice1Text, choice1);
        SetChoice(choice2Root, choice2Text, choice2);
    }

    private void SetChoice(GameObject choiceRoot, TextMeshProUGUI choiceText, string text)
    {
        var visible = text != null && text.Length > 0;
        if (choiceRoot != null)
        {
            choiceRoot.SetActive(visible);
        }

        if (choiceText != null)
        {
            choiceText.text = text;
        }
    }

    private void SetDialogVisible(bool visible)
    {
        if (dialogRoot != null)
        {
            dialogRoot.SetActive(visible);
        }
    }

    private void FaceLocalPlayer()
    {
        if (dialogTransform == null || _localPlayer == null)
        {
            return;
        }

        var target = _localPlayer.GetPosition();
        var direction = dialogTransform.position - target;
        direction.y = 0f;

        if (direction.sqrMagnitude > 0.001f)
        {
            dialogTransform.rotation = Quaternion.LookRotation(direction);
        }
    }
}
