import { ComfyPrompt } from "../..";
import workflow from "./api_workflow.json";
import { getRandomInt } from "@/lib/utils";

export class Img2VideoWithBaseVideoPrompt implements ComfyPrompt {
  /**
   * File input path, Web URL or Data URL (base64url)
   */
  image: string;
  /**
   * Base video. It accepts file input path, Web URL or Data URL (base64url)
   */
  video: string;
  prompt: string;

  constructor({
    image,
    video,
    prompt,
  }: {
    image: string;
    video: string;
    prompt: string;
  }) {
    this.image = image;
    this.video = video;
    this.prompt = prompt;
  }

  getWorkflow() {
    return {
      ...workflow,
      "353": {
        ...workflow["353"],
        inputs: {
          ...workflow["353"].inputs,
          seed: getRandomInt(10000000, 9999999999),
        },
      },
      "52": {
        ...workflow["52"],
        inputs: {
          ...workflow["52"].inputs,
          video: this.video, // base video
        },
      },
      "167": {
        ...workflow["167"],
        inputs: {
          ...workflow["167"].inputs,
          image: this.image, // image
        },
      },
      "336": {
        ...workflow["336"],
        inputs: {
          ...workflow["336"].inputs,
          text: this.prompt,
        },
      },
      "264": {
        ...workflow["264"],
        inputs: {
          ...workflow["264"].inputs,
          value: 720, // Output video width
        },
      },
      "265": {
        ...workflow["265"],
        inputs: {
          ...workflow["265"].inputs,
          value: 1280, // Output video height
        },
      },
    } as typeof workflow;
  }
}
