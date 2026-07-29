import { ComfyPrompt } from "../..";
import workflow from "./api_workflow.json";
import { getRandomInt } from "@/lib/utils";

export class Txt2VideoPrompt implements ComfyPrompt {
  prompt: string;

  constructor({ prompt }: { prompt: string }) {
    this.prompt = prompt;
  }

  getWorkflow() {
    return {
      ...workflow,
      "81": {
        ...workflow["81"],
        inputs: {
          ...workflow["81"].inputs,
          noise_seed: getRandomInt(10000000, 9999999999),
        },
      },
      "89": {
        ...workflow["89"],
        inputs: {
          ...workflow["89"].inputs,
          text: this.prompt,
        },
      },
      "74": {
        ...workflow["74"],
        inputs: {
          ...workflow["74"].inputs,
          height: 640,
          width: 640,
          batch_size: 1,
        },
      },
    } as typeof workflow;
  }
}
