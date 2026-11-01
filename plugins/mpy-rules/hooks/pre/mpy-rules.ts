// omp extension: injects rules/core.md into the session when the working
// directory is a MicroPython checkout. The other rule files are listed by omp
// itself (they carry `description` and `globs` frontmatter) and are read on
// demand with rule://<name>.
//
// Claude Code and Codex ignore this file; they use hooks/hooks.json.
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const MARKERS = ["py/mpconfig.h", "py/runtime.h", "mpy-cross/main.c"];
const PLUGIN_ROOT = resolve(__dirname, "..", "..");

function isMicroPythonRepo(cwd: string): boolean {
	return MARKERS.some((marker) => existsSync(join(cwd, marker)));
}

function stripFrontmatter(text: string): string {
	return text.replace(/^---\n[\s\S]*?\n---\n/, "").trim();
}

function buildMessage(): string {
	const core = stripFrontmatter(readFileSync(join(PLUGIN_ROOT, "rules", "core.md"), "utf8"));
	return [
		"# MicroPython rules (mpy-rules plugin)",
		"",
		core,
		"",
		"## Other MicroPython rule files",
		"",
		"Read a rule with `rule://<name>` before you touch the paths it covers: architecture (py/, extmod/, ports/, lib/, shared/), documentation (docs/**/*.rst), development-patterns (any code), pr-workflow (PR and commit text).",
	].join("\n");
}

export default function mpyRules(pi: any): void {
	let injected = false;

	pi.on("session_start", () => {
		injected = false;
	});
	pi.on("session_switch", () => {
		injected = false;
	});

	pi.on("before_agent_start", (_event: unknown, ctx: { cwd: string }) => {
		if (injected || !isMicroPythonRepo(ctx.cwd)) return;
		injected = true;
		return {
			message: {
				customType: "mpy-rules",
				content: buildMessage(),
				display: false,
			},
		};
	});
}
