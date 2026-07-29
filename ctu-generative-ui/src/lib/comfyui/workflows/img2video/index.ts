import { ComfyPrompt } from "../..";
import workflow from "./api_workflow.json";
import { getRandomInt } from "@/lib/utils";

export class Img2VideoPrompt implements ComfyPrompt {
  /**
   * File input path, Web URL or Data URL (base64url)
   */
  image: string;
  prompt: string;

  constructor({ image, prompt }: { image: string; prompt: string }) {
    this.image = image;
    this.prompt = prompt;
  }

  getWorkflow() {
    return {
      ...workflow,
      "86": {
        ...workflow["86"],
        inputs: {
          ...workflow["86"].inputs,
          noise_seed: getRandomInt(10000000, 9999999999),
        },
      },
      "97": {
        ...workflow["97"],
        inputs: {
          ...workflow["97"].inputs,
          image: this.image,
        },
      },
      "93": {
        ...workflow["93"],
        inputs: {
          ...workflow["93"].inputs,
          text: this.prompt,
        },
      },
      "98": {
        ...workflow["98"],
        inputs: {
          ...workflow["98"].inputs,
          height: 640,
          width: 640,
          batch_size: 1,
        },
      },
    } as typeof workflow;
  }
}
