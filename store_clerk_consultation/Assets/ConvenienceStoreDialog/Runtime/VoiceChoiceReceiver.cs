using TMPro;
using UdonSharp;
using UnityEngine;
using VRC.SDK3.StringLoading;
using VRC.SDKBase;
using VRC.Udon.Common.Interfaces;

public class VoiceChoiceReceiver : UdonSharpBehaviour
{
    public ProximityDialogTrigger dialog;
    public TextMeshProUGUI statusText;
    public VRCUrl pollUrl;
    public float pollIntervalSeconds = 1f;
    public bool enablePolling = true;

    private string _lastVersion = "";
    private float _nextPollTime;
    private bool _requestInFlight;

    private void Start()
    {
        _nextPollTime = Time.time + 0.5f;
    }

    private void Update()
    {
        if (!enablePolling || _requestInFlight || pollUrl == null)
        {
            return;
        }

        if (Time.time < _nextPollTime)
        {
            return;
        }

        _requestInFlight = true;
        _nextPollTime = Time.time + pollIntervalSeconds;
        VRCStringDownloader.LoadUrl(pollUrl, (IUdonEventReceiver)this);
    }

    public override void OnStringLoadSuccess(IVRCStringDownload result)
    {
        _requestInFlight = false;
        HandlePayload(result.Result);
    }

    public override void OnStringLoadError(IVRCStringDownload result)
    {
        _requestInFlight = false;
        if (statusText != null)
        {
            statusText.text = "音声サービスに接続できません";
        }
    }

    private void HandlePayload(string payload)
    {
        if (payload == null || payload.Length < 3)
        {
            return;
        }

        var firstPipe = payload.IndexOf("|");
        if (firstPipe <= 0 || firstPipe + 2 >= payload.Length)
        {
            return;
        }

        var version = payload.Substring(0, firstPipe);
        if (version == _lastVersion)
        {
            return;
        }

        _lastVersion = version;
        var choiceChar = payload.Substring(firstPipe + 1, 1);
        var transcript = ExtractTranscript(payload, firstPipe);

        if (dialog == null)
        {
            return;
        }

        var matched = true;
        if (choiceChar == "0")
        {
            dialog.SelectChoice0();
        }
        else if (choiceChar == "1")
        {
            dialog.SelectChoice1();
        }
        else if (choiceChar == "2")
        {
            dialog.SelectChoice2();
        }
        else
        {
            matched = false;
        }

        if (statusText != null && matched)
        {
            statusText.text = "聞き取り: " + transcript;
        }
        else if (statusText != null)
        {
            statusText.text = "聞き取り: " + transcript + "\nもう一度お願いします";
        }
    }

    private string ExtractTranscript(string payload, int firstPipe)
    {
        var secondPipe = payload.IndexOf("|", firstPipe + 1);
        if (secondPipe < 0 || secondPipe + 1 >= payload.Length)
        {
            return "";
        }

        var thirdPipe = payload.IndexOf("|", secondPipe + 1);
        if (thirdPipe < 0)
        {
            return payload.Substring(secondPipe + 1);
        }

        return payload.Substring(secondPipe + 1, thirdPipe - secondPipe - 1);
    }
}
