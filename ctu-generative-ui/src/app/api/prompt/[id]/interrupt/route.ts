import { NextRequest, NextResponse } from "next/server";

export async function POST(
  req: NextRequest
  // ctx: RouteContext<"/api/prompt/[id]/interrupt">
) {
  // const { id: promptId } = await ctx.params;
  const jobId = req.headers.get("X-Job-ID");
  if (jobId === null)
    return new NextResponse("Missing X-Job-ID header.", { status: 400 });

  //   try {
  //     const data = await ComfyHandler.getPromptStatus({
  //       jobId,
  //       promptId,
  //     });
  //     return NextResponse.json(data.data, {
  //       status: 200,
  //       statusText: data.statusText,
  //     });
  //   } catch (err) {
  //     const error = err as FetchError;
  //     return new NextResponse(error.message, {
  //       status: error.status,
  //       statusText: error.statusText,
  //     });
  //   }
}
