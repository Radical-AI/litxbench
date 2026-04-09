import { NextRequest } from "next/server";
import { spawn, ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const dynamic = "force-dynamic";
export const maxDuration = 300; // 5 minutes max

const MAX_PDF_SIZE = 100 * 1024 * 1024; // 100 MB

function cleanupTempFiles(tmpPath: string, outputDir: string) {
  try { fs.unlinkSync(tmpPath); } catch {}
  try { fs.rmSync(outputDir, { recursive: true, force: true }); } catch {}
}

function killProcess(proc: ChildProcess) {
  try {
    proc.kill("SIGTERM");
    // Force kill after 5 seconds if still alive
    setTimeout(() => {
      try { proc.kill("SIGKILL"); } catch {}
    }, 5000);
  } catch {}
}

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const file = formData.get("pdf") as File | null;
  if (!file) {
    return new Response(JSON.stringify({ error: "No PDF file provided" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (file.size > MAX_PDF_SIZE) {
    return new Response(JSON.stringify({ error: `PDF too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max is 100 MB.` }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Save uploaded PDF to a temp file
  const tmpDir = os.tmpdir();
  const tmpPath = path.join(tmpDir, `litxbench_${Date.now()}_${file.name}`);
  const bytes = await file.arrayBuffer();
  fs.writeFileSync(tmpPath, Buffer.from(bytes));

  // Output dir next to the temp PDF
  const outputDir = path.join(tmpDir, `litxbench_${Date.now()}_${file.name.replace(".pdf", "")}_transcribed`);

  // Spawn the Python script and stream its stdout
  const projectRoot = path.join(process.cwd(), "..");
  const scriptPath = path.join(projectRoot, "scripts", "transcribe_and_extract.py");

  const encoder = new TextEncoder();
  let proc: ChildProcess | null = null;
  let closed = false;

  const stream = new ReadableStream({
    start(controller) {
      proc = spawn("uv", ["run", scriptPath, tmpPath, "--output-dir", outputDir], {
        cwd: projectRoot,
        env: { ...process.env },
        stdio: ["ignore", "pipe", "pipe"],
      });

      proc.stdout!.on("data", (data: Buffer) => {
        if (closed) return;
        try { controller.enqueue(encoder.encode(data.toString())); } catch {}
      });

      proc.stderr!.on("data", (data: Buffer) => {
        if (closed) return;
        // Forward stderr as status events so the UI can show them
        const lines = data.toString().trim().split("\n");
        for (const line of lines) {
          if (line.trim()) {
            try {
              controller.enqueue(
                encoder.encode(JSON.stringify({ event: "log", message: line.trim() }) + "\n")
              );
            } catch {}
          }
        }
      });

      proc.on("close", (code) => {
        if (closed) return;
        closed = true;
        // Clean up temp files
        cleanupTempFiles(tmpPath, outputDir);

        try {
          if (code !== 0) {
            controller.enqueue(
              encoder.encode(JSON.stringify({ event: "error", message: `Process exited with code ${code}` }) + "\n")
            );
          }
          controller.enqueue(encoder.encode(JSON.stringify({ event: "done", exitCode: code }) + "\n"));
          controller.close();
        } catch {}
      });

      proc.on("error", (err) => {
        if (closed) return;
        closed = true;
        cleanupTempFiles(tmpPath, outputDir);
        try {
          controller.enqueue(
            encoder.encode(JSON.stringify({ event: "error", message: err.message }) + "\n")
          );
          controller.close();
        } catch {}
      });
    },
    cancel() {
      // Client disconnected — kill the subprocess to free memory
      closed = true;
      if (proc) killProcess(proc);
      cleanupTempFiles(tmpPath, outputDir);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson",
      "Transfer-Encoding": "chunked",
      "Cache-Control": "no-cache",
    },
  });
}
