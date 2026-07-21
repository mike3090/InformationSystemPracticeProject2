using UdonSharp;
using UnityEngine;

public class ProximityDialogChoiceButton : UdonSharpBehaviour
{
    public ProximityDialogTrigger dialog;
    public int choiceIndex;

    public override void Interact()
    {
        if (dialog == null)
        {
            return;
        }

        if (choiceIndex == 0)
        {
            dialog.SelectChoice0();
        }
        else if (choiceIndex == 1)
        {
            dialog.SelectChoice1();
        }
        else
        {
            dialog.SelectChoice2();
        }
    }
}
