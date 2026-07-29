import { ComfyPrompt } from "../..";
import workflow from "./api_workflow.json";
import { getRandomInt } from "@/lib/utils";

type QwenImageEditWorkflow = Omit<
  typeof workflow,
  "78" | "130" | "138" | "129"
> & {
  "78": (typeof workflow)["78"] | undefined;
  "130": (typeof workflow)["130"] | undefined;
  "138": (typeof workflow)["138"] | undefined;
  "129": Omit<(typeof workflow)["129"], "inputs"> & {
    inputs: Omit<
      (typeof workflow)["129"]["inputs"],
      "image1" | "image2" | "image3"
    > & {
      image1?: Array<string | number>;
      image2?: Array<string | number>;
      image3?: Array<string | number>;
    };
  };
};

export class QwenImageEditPrompt implements ComfyPrompt {
  /**
   * File input path, Web URL or Data URL (base64url)
   */
  images: Array<string | undefined>;
  prompt: string;

  constructor({
    image1,
    image2,
    image3,
    prompt,
  }: {
    image1?: string;
    image2?: string;
    image3?: string;
    prompt: string;
  }) {
    this.prompt = prompt;
    this.images = [image1, image2, image3];
  }

  getWorkflow() {
    const rawPrompt = {
      ...workflow,
      "3": {
        ...workflow["3"],
        inputs: {
          ...workflow["3"].inputs,
          seed: getRandomInt(10000000, 9999999999),
        },
      },
      "78": {
        ...workflow["78"],
        inputs: {
          ...workflow["78"].inputs,
          image: this.images.at(0), // image 1
        },
      },
      "130": {
        ...workflow["130"],
        inputs: {
          ...workflow["130"].inputs,
          image: this.images.at(1), // image 2
        },
      },
      "138": {
        ...workflow["138"],
        inputs: {
          ...workflow["138"].inputs,
          image: this.images.at(2), // image 3
        },
      },
      "129": {
        ...workflow["129"],
        inputs: {
          ...workflow["129"].inputs,
          prompt: this.prompt,
        },
      },
      "101": {
        ...workflow["101"],
        inputs: {
          ...workflow["101"].inputs,
          height: 1024,
          width: 1024,
          batch_size: 1,
        },
      },
    } as QwenImageEditWorkflow;
    return this.normalizePrompt(rawPrompt);
  }

  private normalizePrompt(prompt: QwenImageEditWorkflow) {
    const imgKeys: Array<
      | { nodeId: "78"; propName: "image1" }
      | { nodeId: "130"; propName: "image2" }
      | { nodeId: "138"; propName: "image3" }
    > = [
      { nodeId: "78", propName: "image1" },
      { nodeId: "130", propName: "image2" },
      { nodeId: "138", propName: "image3" },
    ];
    const mainKey = "129";

    let result = { ...prompt };
    for (const key of imgKeys) {
      if (!result[key.nodeId]?.inputs?.image) {
        delete result[key.nodeId];
        delete result[mainKey].inputs[key.propName];
      }
    }

    return result;
  }
}
