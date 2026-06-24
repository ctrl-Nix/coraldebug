#!/usr/bin/env node
/**
 * cli/src/index.ts
 *
 * Thin, fast CLI shell over the Python agent engine. Kept deliberately dumb:
 * this layer owns UX (colors, spinner, output formatting), the Python layer
 * owns all model/agent logic. Don't let business logic creep in here.
 */

import { spawn } from "child_process";
import * as fs from "fs";
import * as path from "path";

interface AgentResult {
  agent: string;
  verdict: "approve" | "request_changes" | "block";
  confidence: number;
  reasoning: string;
}

interface ReviewResult {
  final_verdict: string;
  final_confidence: number;
  overruled: boolean;
  specialists: AgentResult[];
  skeptic: AgentResult;
}

const VERDICT_COLOR: Record<string, string> = {
  approve: "\x1b[32m",        // green
  request_changes: "\x1b[33m", // yellow
  block: "\x1b[31m",          // red
};
const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";

function runPythonReview(diffPath: string): Promise<ReviewResult> {
  return new Promise((resolve, reject) => {
    const pyEntry = path.join(__dirname, "..", "..", "review_cli.py");
    const proc = spawn("python3", [pyEntry, "--diff", diffPath, "--json"]);

    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => (stdout += d.toString()));
    proc.stderr.on("data", (d) => (stderr += d.toString()));

    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`Python engine exited with code ${code}: ${stderr}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (err) {
        reject(new Error(`Failed to parse engine output: ${stdout}`));
      }
    });
  });
}

function printResult(result: ReviewResult) {
  const color = VERDICT_COLOR[result.final_verdict] || "";
  console.log(
    `\n${BOLD}SwarmReview verdict:${RESET} ${color}${result.final_verdict.toUpperCase()}${RESET} ` +
      `(confidence ${result.final_confidence})${result.overruled ? "  [overruled by skeptic]" : ""}\n`
  );

  for (const s of result.specialists) {
    const c = VERDICT_COLOR[s.verdict] || "";
    console.log(`  ${BOLD}${s.agent}${RESET}: ${c}${s.verdict}${RESET} (${s.confidence})`);
    console.log(`    ${s.reasoning}`);
  }

  const sk = result.skeptic;
  const skColor = VERDICT_COLOR[sk.verdict] || "";
  console.log(`\n  ${BOLD}skeptic${RESET}: ${skColor}${sk.verdict}${RESET} (${sk.confidence})`);
  console.log(`    ${sk.reasoning}\n`);
}

async function main() {
  const diffPath = process.argv[2];
  if (!diffPath) {
    console.error("Usage: swarmreview <path-to-diff-file>");
    process.exit(1);
  }
  if (!fs.existsSync(diffPath)) {
    console.error(`File not found: ${diffPath}`);
    process.exit(1);
  }

  try {
    const result = await runPythonReview(diffPath);
    printResult(result);
    process.exit(result.final_verdict === "block" ? 1 : 0);
  } catch (err) {
    console.error("SwarmReview failed:", (err as Error).message);
    process.exit(2);
  }
}

main();
