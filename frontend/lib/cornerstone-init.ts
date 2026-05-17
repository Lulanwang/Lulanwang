"use client";

/**
 * One-time global initialization for Cornerstone3D.
 *
 * Cornerstone is heavy and stateful. We do all init lazily on first
 * viewer mount, guarded by a singleton promise so React strict-mode
 * double-mount doesn't double-init.
 *
 * The DICOM image loader is configured with a custom XHR header
 * provider so every WADO-RS request includes our JWT — this is what
 * makes the audit log on the FastAPI DICOMweb proxy work.
 */
import * as cornerstone from "@cornerstonejs/core";
import { init as csInit, type Types } from "@cornerstonejs/core";
import { init as csToolsInit, addTool, ToolGroupManager, PanTool, ZoomTool, WindowLevelTool, StackScrollTool, LengthTool, RectangleROITool, EllipticalROITool, BrushTool, RectangleScissorsTool, segmentation as csSeg } from "@cornerstonejs/tools";
import cornerstoneDICOMImageLoader from "@cornerstonejs/dicom-image-loader";
import dicomParser from "dicom-parser";

let initPromise: Promise<void> | null = null;

export const TOOL_NAMES = {
  Pan: "Pan",
  Zoom: "Zoom",
  WindowLevel: "WindowLevel",
  StackScroll: "StackScroll",
  Length: "Length",
  RectangleROI: "RectangleROI",
  EllipticalROI: "EllipticalROI",
  Brush: "Brush",
  RectangleScissors: "RectangleScissors",
} as const;

export type ToolName = keyof typeof TOOL_NAMES;

export const TOOL_GROUP_ID = "lulan-default";

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("lulan_token");
  return token
    ? { Authorization: `Bearer ${token}`, Accept: "application/dicom+json" }
    : { Accept: "application/dicom+json" };
}

export function ensureCornerstone(): Promise<void> {
  if (initPromise) return initPromise;
  initPromise = (async () => {
    await csInit();
    await csToolsInit();

    // The DICOM image loader bundle calls `cornerstone.registerImageLoader`,
    // `cornerstone.metaData.addProvider`, `cornerstone.utilities.isVideoTransferSyntax`,
    // etc. as top-level methods, so we pass the entire core namespace —
    // not the {metaData, imageLoader} subset we used to.
    cornerstoneDICOMImageLoader.external.cornerstone = cornerstone;
    cornerstoneDICOMImageLoader.external.dicomParser = dicomParser;
    cornerstoneDICOMImageLoader.configure({
      useWebWorkers: true,
      decodeConfig: { convertFloatPixelDataToInt: false },
      beforeSend: (xhr: XMLHttpRequest) => {
        const headers = getAuthHeaders();
        for (const [k, v] of Object.entries(headers)) xhr.setRequestHeader(k, v);
      },
    });

    // Worker pool for codec decoding
    const config = {
      maxWebWorkers: Math.max(1, Math.min(navigator.hardwareConcurrency || 1, 4)),
      startWebWorkersOnDemand: true,
      taskConfiguration: {
        decodeTask: { initializeCodecsOnStartup: false },
      },
    };
    cornerstoneDICOMImageLoader.webWorkerManager.initialize(config);

    // Register every tool we expose in the toolbar.
    addTool(PanTool);
    addTool(ZoomTool);
    addTool(WindowLevelTool);
    addTool(StackScrollTool);
    addTool(LengthTool);
    addTool(RectangleROITool);
    addTool(EllipticalROITool);
    addTool(BrushTool);
    addTool(RectangleScissorsTool);
  })();
  return initPromise;
}

export function getOrCreateToolGroup() {
  let group = ToolGroupManager.getToolGroup(TOOL_GROUP_ID);
  if (group) return group;
  group = ToolGroupManager.createToolGroup(TOOL_GROUP_ID)!;
  group.addTool(TOOL_NAMES.Pan);
  group.addTool(TOOL_NAMES.Zoom);
  group.addTool(TOOL_NAMES.WindowLevel);
  group.addTool(TOOL_NAMES.StackScroll);
  group.addTool(TOOL_NAMES.Length);
  group.addTool(TOOL_NAMES.RectangleROI);
  group.addTool(TOOL_NAMES.EllipticalROI);
  group.addTool(TOOL_NAMES.Brush);
  group.addTool(TOOL_NAMES.RectangleScissors);
  // Defaults: passive everywhere, WL active on left button until user picks a tool
  group.setToolActive(TOOL_NAMES.WindowLevel, { bindings: [{ mouseButton: 1 }] });
  group.setToolActive(TOOL_NAMES.Pan, { bindings: [{ mouseButton: 2 }] });
  group.setToolActive(TOOL_NAMES.Zoom, { bindings: [{ mouseButton: 4 }] });
  group.setToolActive(TOOL_NAMES.StackScroll, { bindings: [{ mouseWheel: true } as any] });
  return group;
}

export function setActiveTool(toolName: string) {
  const group = ToolGroupManager.getToolGroup(TOOL_GROUP_ID);
  if (!group) return;
  // Disable mouse-1 bindings on every tool so only the picked one owns left-click
  for (const name of Object.values(TOOL_NAMES)) {
    if (name === toolName) continue;
    try {
      group.setToolPassive(name);
    } catch {}
  }
  group.setToolActive(toolName, { bindings: [{ mouseButton: 1 }] });
}

export type { Types };
export { csSeg as segmentation };
