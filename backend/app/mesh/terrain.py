"""
DepthWizard 3D Terrain Mesh Module
==================================
Converts real predicted 2D elevation/depth arrays into 3D triangular surface meshes.
Strictly adheres to .agents/rules/depthwizard-development.md:
- Mesh vertices are strictly derived from real model predictions or calibrated DSMs.
- Zero synthetic/random elevation displacement.
- Supports Wavefront OBJ and NumPy array export with full texture coordinate mapping.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import cv2


@dataclass
class TerrainMesh:
    """
    In-memory representation of a 3D terrain surface mesh.
    """
    vertices: np.ndarray        # Shape (N, 3), float32 (X, Y, Z)
    faces: np.ndarray           # Shape (M, 3), int32 (1-based or 0-based vertex indices)
    normals: np.ndarray         # Shape (N, 3), float32 normal vectors
    uvs: np.ndarray             # Shape (N, 2), float32 texture coordinates [0, 1]
    grid_shape: Tuple[int, int] # (rows, cols) of downsampled mesh
    is_metric: bool             # True if vertical units are meters, False if relative [0, 1]
    vertex_count: int
    face_count: int


class TerrainMeshGenerator:
    """
    Deterministic 3D terrain mesh generation from raster elevation data.
    """

    @staticmethod
    def generate_mesh(
        elevation_map: np.ndarray,
        max_resolution: int = 256,
        vertical_scale: float = 1.0,
        is_metric: bool = False,
        xy_scale: float = 1.0,
    ) -> TerrainMesh:
        """
        Generate a 3D terrain mesh from a 2D elevation/depth array.

        Args:
            elevation_map: 2D float32 array of relative depth or calibrated elevation
            max_resolution: Maximum grid dimension along height/width to protect memory
            vertical_scale: Vertical exaggeration multiplier (default 1.0)
            is_metric: Whether elevation is in real meters (vs relative [0, 1])
            xy_scale: Horizontal coordinate spacing multiplier

        Returns:
            TerrainMesh dataclass with vertices, faces, normals, and UVs
        """
        if elevation_map.ndim != 2:
            raise ValueError(f"Elevation map must be 2D, got shape {elevation_map.shape}")

        if np.isnan(elevation_map).any() or np.isinf(elevation_map).any():
            raise ValueError("Elevation map contains NaN or Inf values; cannot construct mesh.")

        h, w = elevation_map.shape

        # Downsample grid if exceeding max_resolution to keep memory bounded on i3 CPU
        target_h, target_w = h, w
        if max(h, w) > max_resolution:
            scale = max_resolution / float(max(h, w))
            target_w = max(4, int(round(w * scale)))
            target_h = max(4, int(round(h * scale)))
            # Bilinear interpolation preserves continuous elevation surfaces
            grid_elev = cv2.resize(
                elevation_map.astype(np.float32),
                (target_w, target_h),
                interpolation=cv2.INTER_LINEAR
            )
        else:
            grid_elev = elevation_map.astype(np.float32)

        rows, cols = grid_elev.shape
        num_vertices = rows * cols

        # 1. Compute Vertices (X, Y, Z)
        # Coordinate system: X -> East (cols), Y -> North (rows, inverted for GIS convention), Z -> Up
        x_coords = np.linspace(0.0, (cols - 1) * xy_scale, cols, dtype=np.float32)
        y_coords = np.linspace((rows - 1) * xy_scale, 0.0, rows, dtype=np.float32)

        grid_x, grid_y = np.meshgrid(x_coords, y_coords)
        grid_z = grid_elev * float(vertical_scale)

        # Center mesh horizontally around (0, 0)
        grid_x -= (cols - 1) * xy_scale / 2.0
        grid_y -= (rows - 1) * xy_scale / 2.0

        vertices = np.stack([grid_x.ravel(), grid_y.ravel(), grid_z.ravel()], axis=1)

        # 2. Compute UV Texture Coordinates [0.0, 1.0]
        u_coords = np.linspace(0.0, 1.0, cols, dtype=np.float32)
        v_coords = np.linspace(1.0, 0.0, rows, dtype=np.float32) # 1.0 at top row
        grid_u, grid_v = np.meshgrid(u_coords, v_coords)
        uvs = np.stack([grid_u.ravel(), grid_v.ravel()], axis=1)

        # 3. Construct Triangular Faces
        # For each quad (r, c), create 2 triangles
        r_idx = np.arange(rows - 1)[:, None]
        c_idx = np.arange(cols - 1)[None, :]

        v_top_left = (r_idx * cols + c_idx).ravel()
        v_top_right = (r_idx * cols + (c_idx + 1)).ravel()
        v_bot_left = ((r_idx + 1) * cols + c_idx).ravel()
        v_bot_right = ((r_idx + 1) * cols + (c_idx + 1)).ravel()

        # Triangle 1: top-left, bot-left, top-right
        tri1 = np.stack([v_top_left, v_bot_left, v_top_right], axis=1)
        # Triangle 2: top-right, bot-left, bot-right
        tri2 = np.stack([v_top_right, v_bot_left, v_bot_right], axis=1)

        faces = np.concatenate([tri1, tri2], axis=0).astype(np.int32)

        # 4. Compute Smooth Vertex Normals
        normals = np.zeros_like(vertices, dtype=np.float32)

        # Compute face normals
        v0 = vertices[faces[:, 0]]
        v1 = vertices[faces[:, 1]]
        v2 = vertices[faces[:, 2]]
        face_normals = np.cross(v1 - v0, v2 - v0)
        face_lens = np.linalg.norm(face_normals, axis=1, keepdims=True)
        face_lens[face_lens == 0] = 1.0
        face_normals /= face_lens

        # Accumulate face normals into vertices
        np.add.at(normals, faces[:, 0], face_normals)
        np.add.at(normals, faces[:, 1], face_normals)
        np.add.at(normals, faces[:, 2], face_normals)

        # Normalize vertex normals
        vert_lens = np.linalg.norm(normals, axis=1, keepdims=True)
        vert_lens[vert_lens == 0] = 1.0
        normals /= vert_lens

        return TerrainMesh(
            vertices=vertices,
            faces=faces,
            normals=normals,
            uvs=uvs,
            grid_shape=(rows, cols),
            is_metric=is_metric,
            vertex_count=num_vertices,
            face_count=len(faces)
        )

    @staticmethod
    def export_to_obj(
        mesh: TerrainMesh,
        filepath: Path,
        texture_name: Optional[str] = None
    ) -> Path:
        """
        Export a TerrainMesh to a standard Wavefront OBJ file.

        Args:
            mesh: TerrainMesh instance
            filepath: Destination Path for .obj
            texture_name: Optional filename of companion texture image

        Returns:
            Absolute Path to written .obj file
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.append("# DepthWizard 3D Terrain Mesh")
        lines.append("# Scientific Single-View Elevation Pipeline (SIH 2026)")
        lines.append(f"# Grid Dimensions: {mesh.grid_shape[1]}x{mesh.grid_shape[0]}")
        lines.append(f"# Vertices: {mesh.vertex_count:,}, Faces: {mesh.face_count:,}")
        lines.append(f"# Vertical Units: {'Meters (Calibrated)' if mesh.is_metric else 'Relative [0, 1]'}")

        if texture_name:
            mtl_name = filepath.stem + ".mtl"
            lines.append(f"mtllib {mtl_name}")
            lines.append("usemtl TerrainMaterial")

        # 1. Vertices (v x y z)
        for v in mesh.vertices:
            lines.append(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}")

        # 2. Texture Coordinates (vt u v)
        for uv in mesh.uvs:
            lines.append(f"vt {uv[0]:.5f} {uv[1]:.5f}")

        # 3. Normals (vn nx ny nz)
        for n in mesh.normals:
            lines.append(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}")

        # 4. Faces (f v/vt/vn ...) 1-indexed in OBJ format
        # In our mesh, vertex index, uv index, and normal index match 1:1
        for f in mesh.faces:
            i0, i1, i2 = f[0] + 1, f[1] + 1, f[2] + 1
            lines.append(f"f {i0}/{i0}/{i0} {i1}/{i1}/{i1} {i2}/{i2}/{i2}")

        with open(filepath, "w", encoding="utf-8") as f_out:
            f_out.write("\n".join(lines) + "\n")

        # Write companion MTL file if texture specified
        if texture_name:
            mtl_path = filepath.parent / (filepath.stem + ".mtl")
            mtl_lines = [
                "# DepthWizard Material Definition",
                "newmtl TerrainMaterial",
                "Ka 0.2 0.2 0.2",
                "Kd 0.9 0.9 0.9",
                "Ks 0.1 0.1 0.1",
                "d 1.0",
                "illum 2",
                f"map_Kd {texture_name}"
            ]
            with open(mtl_path, "w", encoding="utf-8") as f_mtl:
                f_mtl.write("\n".join(mtl_lines) + "\n")

        return filepath

