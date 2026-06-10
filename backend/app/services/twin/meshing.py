"""Voxel mask → manifold mesh → glTF-binary.

The pipeline is intentionally defensive: smooth the *mask field* with a
Gaussian before marching cubes (anti-aliases voxel staircase far better
than post-hoc surface smoothing), keep only the largest component to
kill speckle islands, decimate to a fixed face budget, and Taubin-smooth
(no volume shrink, unlike Laplacian). Hard caps mean no input mask can
produce an unbounded mesh.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import trimesh
from scipy import ndimage as ndi
from skimage import measure

from app.services.twin import config as cfg

log = logging.getLogger(__name__)


@dataclass
class StructureMesh:
    name: str
    kind: str                       # "organ" | "lesion"
    color_hex: str
    mesh: trimesh.Trimesh
    volume_cm3: float               # from the input mask, not the mesh
    synthetic_marker: bool = False
    synthetic_extrusion: bool = False

    @property
    def metadata(self) -> dict:
        b = self.mesh.bounds.tolist() if self.mesh is not None else None
        return {
            "name": self.name,
            "kind": self.kind,
            "color": self.color_hex,
            "volume_cm3": round(float(self.volume_cm3), 2),
            "vertices": int(len(self.mesh.vertices)),
            "faces": int(len(self.mesh.faces)),
            "bounds_mm": b,
            "synthetic_marker": self.synthetic_marker,
            "synthetic_extrusion": self.synthetic_extrusion,
        }


@dataclass
class SceneResult:
    glb_bytes: bytes
    structures: list[StructureMesh] = field(default_factory=list)

    @property
    def metadata(self) -> list[dict]:
        return [s.metadata for s in self.structures]


# ---------------------------------------------------------------------------
# Single-mask → trimesh
# ---------------------------------------------------------------------------


def mask_to_mesh(
    mask: np.ndarray,
    spacing_zyx: tuple[float, float, float],
    *,
    face_budget: int,
    smooth_sigma: float = cfg.MASK_SIGMA,
    extrude_z_mm: float | None = None,
) -> trimesh.Trimesh | None:
    """Convert a boolean mask to a watertight, decimated, smoothed mesh.

    ``extrude_z_mm`` synthesizes Z depth for a single-slice 2D mask
    (mammography "billboard" path). Without it, a Z=1 mask has no
    isosurface and marching cubes returns nothing.

    Returns ``None`` when the mask has no foreground voxels or marching
    cubes produces no triangles.
    """
    if mask.size == 0 or not mask.any():
        return None

    sz, sy, sx = spacing_zyx
    work = mask.astype(np.float32)

    if work.shape[0] == 1 and extrude_z_mm:
        # Pad the slab on both sides so marching cubes finds a closed
        # surface (top and bottom). The padded volume's effective Z
        # voxel count gives the slab its thickness; spacing is set to
        # extrude_z_mm / pad_layers.
        pad_layers = 5
        slab = np.broadcast_to(work[0], (pad_layers, work.shape[1], work.shape[2])).copy()
        # Zero the outer planes so the surface closes.
        slab[0] = 0.0
        slab[-1] = 0.0
        work = slab
        sz = float(extrude_z_mm) / pad_layers

    # Gaussian-smooth the mask field for clean isosurfaces.
    if smooth_sigma > 0:
        field = ndi.gaussian_filter(work, sigma=smooth_sigma)
    else:
        field = work

    try:
        verts, faces, normals, _values = measure.marching_cubes(
            field,
            level=0.5,
            spacing=(sz, sy, sx),
            allow_degenerate=False,
        )
    except (RuntimeError, ValueError) as exc:
        log.warning("marching_cubes failed: %s", exc)
        return None
    if verts.size == 0 or faces.size == 0:
        return None

    # marching_cubes returns vertices in (z, y, x) mm. Reorient to glTF
    # (x, y, z) with +Y up by flipping Y. The Y-flip is a reflection,
    # which inverts triangle winding — swap face indices so normals
    # keep pointing outward (`mesh.volume` stays positive, lighting
    # works in three.js).
    verts = np.stack([verts[:, 2], -verts[:, 1], verts[:, 0]], axis=1)
    faces = faces[:, ::-1]

    mesh = trimesh.Trimesh(vertices=verts, faces=faces, vertex_normals=None, process=False)
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    # Keep only the largest connected component to kill speckle. Rank
    # by absolute volume so an inverted-winding piece doesn't lose.
    pieces = mesh.split(only_watertight=False)
    if len(pieces) > 1:
        mesh = max(
            pieces,
            key=lambda m: abs(float(m.volume)) if m.faces.size else 0.0,
        )

    # Decimate to budget.
    if len(mesh.faces) > face_budget:
        try:
            mesh = mesh.simplify_quadric_decimation(face_count=face_budget)
        except Exception as exc:  # noqa: BLE001
            log.warning("decimation failed: %s", exc)

    # Taubin smoothing (volume-preserving).
    try:
        trimesh.smoothing.filter_taubin(
            mesh,
            lamb=cfg.TAUBIN_LAMBDA,
            nu=cfg.TAUBIN_MU,
            iterations=cfg.TAUBIN_ITERATIONS,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("taubin smoothing failed: %s", exc)

    if len(mesh.faces) == 0:
        return None
    return mesh


# ---------------------------------------------------------------------------
# Scene assembly + GLB export
# ---------------------------------------------------------------------------


def _apply_color(mesh: trimesh.Trimesh, hex_color: str, *, opacity: float) -> None:
    rgba = _hex_to_rgba(hex_color, opacity)
    mesh.visual = trimesh.visual.ColorVisuals(
        mesh=mesh, face_colors=np.tile(rgba, (len(mesh.faces), 1))
    )


def _hex_to_rgba(hex_color: str, opacity: float) -> np.ndarray:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    a = int(round(opacity * 255))
    return np.array([r, g, b, a], dtype=np.uint8)


def build_scene(structures: Sequence[StructureMesh]) -> trimesh.Scene:
    scene = trimesh.Scene()
    for s in structures:
        if s.mesh is None or len(s.mesh.faces) == 0:
            continue
        opacity = cfg.ORGAN_OPACITY if s.kind == "organ" else 1.0
        _apply_color(s.mesh, s.color_hex, opacity=opacity)
        scene.add_geometry(s.mesh, geom_name=s.name, node_name=s.name)
    return scene


def export_glb(scene: trimesh.Scene) -> bytes:
    """Serialize a trimesh.Scene as glTF-binary."""
    if not scene.geometry:
        # trimesh refuses to export an empty scene; emit a 1-triangle
        # placeholder so the API can still return a valid GLB rather
        # than a 500. The page will surface "no structures generated".
        placeholder = trimesh.Trimesh(
            vertices=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float),
            faces=np.array([[0, 1, 2]], dtype=np.int64),
        )
        scene = trimesh.Scene(placeholder)
    buf = io.BytesIO()
    scene.export(file_obj=buf, file_type="glb")
    return buf.getvalue()


def assemble_glb(structures: Sequence[StructureMesh]) -> SceneResult:
    """Build scene → GLB → optionally re-decimate organ if over budget."""
    scene = build_scene(structures)
    glb = export_glb(scene)
    if len(glb) <= cfg.GLB_BYTES_CEILING:
        return SceneResult(glb_bytes=glb, structures=list(structures))

    # Over budget — re-decimate the organ once to half the face budget
    # and re-export.
    log.warning(
        "GLB over %d bytes (%d); re-decimating organ",
        cfg.GLB_BYTES_CEILING,
        len(glb),
    )
    for s in structures:
        if s.kind == "organ" and len(s.mesh.faces) > cfg.ORGAN_FACE_BUDGET // 2:
            try:
                s.mesh = s.mesh.simplify_quadric_decimation(
                    face_count=cfg.ORGAN_FACE_BUDGET // 2
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("re-decimation failed: %s", exc)
    scene = build_scene(structures)
    glb = export_glb(scene)
    return SceneResult(glb_bytes=glb, structures=list(structures))
