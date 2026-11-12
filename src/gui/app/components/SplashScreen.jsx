import Button from "@mui/material/Button";
import CloseSharpIcon from '@mui/icons-material/CloseSharp';

export function SplashScreen({onClick}) {
  return (
    <div className="splash-screen">
      <Button className={"close"} onClick={onClick}>
        <CloseSharpIcon />
      </Button>
      <div className="splash-content">
        <h1>QUEUE MANAGER PLUS</h1>
        <h4 className={"sub"}>Version: v0.2.1</h4>
        <h4 className={"sub"}>Released: 18<sup>th</sup> October 2026</h4>
        <h2>What it does</h2>
        <p>Keeps a queue of ComfyUI jobs so you can reorder them, pause the queue, archive jobs for later, and edit a job before it runs.</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>Edit the prompt, and the duration when the workflow has one, on a queued or archived job.</li>
          <li>Show how far the current job has got, including the stage that is running.</li>
          <li>Colour a job when it has been moved ahead of the order it was queued.</li>
          <li>Give every job from the same workflow the same colour.</li>
          <li>Drag across several jobs, then drag a handle to move that group together.</li>
        </ul>
        <p><br/>
          <i>For more details check the <a href={"https://github.com/amaltunga/queue-manager-plus#plus-manual"} target={"_blank"}>Plus manual</a>.</i><br/>
          <i>For full Release Notes view <a href={"https://github.com/QuietNoise/comfyui_queue_manager/blob/main/CHANGELOG.md"} target={"_blank"}>Changelog</a>.</i><br />
          <i>Leave a feedback or report an issue here <a href={"https://github.com/QuietNoise/comfyui_queue_manager/issues"} target={"_blank"}>Issues</a>. </i>
        </p>

      </div>
    </div>
  );
}
