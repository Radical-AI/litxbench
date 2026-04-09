import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

// Cache the parsed graph data so we don't re-read and re-parse on every request
let cachedData: unknown = null;
let cachedMtime: number = 0;

export async function GET() {
  const graphPath = path.join(process.cwd(), "public", "data", "litxalloy_graph.json");

  if (!fs.existsSync(graphPath)) {
    return NextResponse.json(
      { error: "litxalloy_graph.json not found" },
      { status: 404 }
    );
  }

  const mtime = fs.statSync(graphPath).mtimeMs;
  if (!cachedData || mtime !== cachedMtime) {
    cachedData = JSON.parse(fs.readFileSync(graphPath, "utf-8"));
    cachedMtime = mtime;
  }

  return NextResponse.json(cachedData);
}
