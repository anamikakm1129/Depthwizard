"""
Unit and Integration Tests for DepthWizard 3D Terrain Mesh Generator
====================================================================
Tests terrain mesh generation, vertex/face indexing, normal vector computation,
OBJ and MTL export, and validation against corrupt/NaN values.
Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile

from backend.app.mesh.terrain import TerrainMeshGenerator, TerrainMesh

def test_mesh_generation_dimensions_and_counts():
    """Verify exact vertex and face count formulas for a regular height grid."""
    h, w = 12, 16
    grid = np.linspace(0.0, 1.0, h * w, dtype=np.float32).reshape(h, w)

    mesh = TerrainMeshGenerator.generate_mesh(
        elevation_map=grid,
        max_resolution=256,
        vertical_scale=1.5,
        is_metric=False,
        xy_scale=1.0
    )

    expected_vertices = h * w
    expected_faces = (h - 1) * (w - 1) * 2

    assert mesh.vertex_count == expected_vertices
    assert mesh.face_count == expected_faces
    assert mesh.vertices.shape == (expected_vertices, 3)
    assert mesh.faces.shape == (expected_faces, 3)
    assert mesh.normals.shape == (expected_vertices, 3)
    assert mesh.uvs.shape == (expected_vertices, 2)
    assert mesh.is_metric is False

    # Check UV range
    assert np.all(mesh.uvs >= 0.0)
    assert np.all(mesh.uvs <= 1.0)

    # Check normal vectors are normalized
    norms = np.linalg.norm(mesh.normals, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-4)

def test_mesh_downsampling_limits():
    """Verify mesh resolution is capped to protect memory on CPU systems."""
    h, w = 400, 300
    large_grid = np.random.RandomState(42).uniform(0, 100, (h, w)).astype(np.float32)

    max_res = 80
    mesh = TerrainMeshGenerator.generate_mesh(
        elevation_map=large_grid,
        max_resolution=max_res,
        vertical_scale=1.0
    )

    assert max(mesh.grid_shape) <= max_res
    assert mesh.vertex_count == mesh.grid_shape[0] * mesh.grid_shape[1]
    assert mesh.face_count == (mesh.grid_shape[0] - 1) * (mesh.grid_shape[1] - 1) * 2

def test_mesh_rejects_nan_and_inf():
    """Verify generator strictly rejects invalid raster values."""
    nan_grid = np.ones((20, 20), dtype=np.float32)
    nan_grid[5, 5] = np.nan
    with pytest.raises(ValueError, match="NaN or Inf"):
        TerrainMeshGenerator.generate_mesh(nan_grid)

    inf_grid = np.ones((20, 20), dtype=np.float32)
    inf_grid[10, 10] = np.inf
    with pytest.raises(ValueError, match="NaN or Inf"):
        TerrainMeshGenerator.generate_mesh(inf_grid)

def test_mesh_obj_export():
    """Verify Wavefront OBJ file format correctness, 1-based indexing, and MTL creation."""
    h, w = 8, 10
    grid = np.sin(np.linspace(0, np.pi, h)[:, None]) * np.cos(np.linspace(0, np.pi, w)[None, :])
    grid = grid.astype(np.float32)

    mesh = TerrainMeshGenerator.generate_mesh(
        elevation_map=grid,
        max_resolution=256,
        vertical_scale=2.0,
        is_metric=True
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        obj_path = Path(tmpdir) / "terrain_test.obj"
        exported = TerrainMeshGenerator.export_to_obj(
            mesh=mesh,
            filepath=obj_path,
            texture_name="texture.png"
        )

        assert exported.exists()
        content = obj_path.read_text(encoding="utf-8")

        # Verify companion MTL file
        mtl_path = Path(tmpdir) / "terrain_test.mtl"
        assert mtl_path.exists()
        mtl_content = mtl_path.read_text(encoding="utf-8")
        assert "map_Kd texture.png" in mtl_content
        assert "mtllib terrain_test.mtl" in content

        # Count OBJ elements
        lines = content.strip().split("\n")
        v_lines = [l for l in lines if l.startswith("v ")]
        vt_lines = [l for l in lines if l.startswith("vt ")]
        vn_lines = [l for l in lines if l.startswith("vn ")]
        f_lines = [l for l in lines if l.startswith("f ")]

        assert len(v_lines) == mesh.vertex_count
        assert len(vt_lines) == mesh.vertex_count
        assert len(vn_lines) == mesh.vertex_count
        assert len(f_lines) == mesh.face_count

        # Check face indices are 1-based and within valid range
        first_face = f_lines[0].split()[1:]
        indices = [int(tok.split("/")[0]) for tok in first_face]
        assert all(1 <= idx <= mesh.vertex_count for idx in indices)

