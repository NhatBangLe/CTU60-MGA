export interface ImageTemplate {
  id: string;
  name: string;
  description?: string;
  prompt: string;
  image: {
    fileName: string;
    mimeType: string;
    subfolder?: string;
  };
}

export interface BaseSuggestion {
  id: string;
  type: "text" | "image";
  suggestion: string;
}

export interface TextPromptSuggestion extends BaseSuggestion {
  type: Extract<BaseSuggestion["type"], "text">;
}

export interface ImageTemplateSuggestion
  extends
    Omit<ImageTemplate, "image" | "prompt" | "description">,
    BaseSuggestion {
  type: Extract<BaseSuggestion["type"], "image">;
  template: {
    id: string;
    groupId: string;
  };
}

export interface ImageTemplateGroup {
  id: string;
  name: string;
  templates: ImageTemplate[];
}

export function buildImageSrc({
  fileName,
  subfolder,
}: {
  fileName: string;
  subfolder?: string;
}) {
  return `/templates/${subfolder ? `${subfolder}/` : ""}${fileName}`;
}

export const templateSuggestions: Array<
  TextPromptSuggestion | ImageTemplateSuggestion
> = [
  {
    id: "founded-year",
    type: "text",
    suggestion: "Trường Đại học Cần Thơ thành lập vào năm nào?",
  },
  {
    id: "the-first-rector",
    type: "text",
    suggestion: "Hiệu trưởng đầu tiên của Đại học Cần Thơ là ai?",
  },
  {
    id: "remembered-milestones",
    type: "text",
    suggestion:
      "Các cột mốc đáng nhớ trong suốt 60 năm qua của Đại học Cần Thơ là gì?",
  },
  // {
  //   id: "hoi_truong_rua_1",
  //   type: "image",
  //   suggestion: "Tạo ảnh với Sân trước Hội trường rùa",
  //   name: "Sân trước",
  //   template: {
  //     id: "hoi_truong_rua_1",
  //     groupId: "hoi_truong_rua",
  //   },
  // },
];

import configTemplates from "./templates.json";
export const templateGroups: ImageTemplateGroup[] = configTemplates;
