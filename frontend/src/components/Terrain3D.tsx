import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { Box, RotateCcw, Sliders } from 'lucide-react';
import { getDownloadUrl } from '../services/api';

interface Terrain3DProps {
  originalImageUrl: string;
  depthImageUrl: string;
  depthType: string;
  isMetric: boolean;
}

export const Terrain3D: React.FC<Terrain3DProps> = ({
  originalImageUrl,
  depthImageUrl,
  depthType,
  isMetric,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [verticalScale, setVerticalScale] = useState<number>(1.0);
  const [wireframe, setWireframe] = useState<boolean>(false);
  const [textureMode, setTextureMode] = useState<'optical' | 'depth' | 'shaded'>('optical');
  const [isLoadingMesh, setIsLoadingMesh] = useState<boolean>(true);

  // References to Three.js instances for dynamic updates
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);
  const baseHeightsRef = useRef<Float32Array | null>(null);
  const opticalTextureRef = useRef<THREE.Texture | null>(null);
  const depthTextureRef = useRef<THREE.Texture | null>(null);
  const animationFrameIdRef = useRef<number | null>(null);

  const fullDepthUrl = getDownloadUrl(depthImageUrl);

  useEffect(() => {
    if (!mountRef.current) return;

    const container = mountRef.current;
    const width = container.clientWidth || 700;
    const height = 480;

    // 1. Scene & Camera setup
    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color(0x070a13);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 2000);
    camera.position.set(0, -110, 85);
    camera.up.set(0, 0, 1); // Z is vertical elevation in GIS convention
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // 2. WebGL Renderer optimized for Intel HD 520
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'default' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.shadowMap.enabled = false;
    container.innerHTML = '';
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 3. Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 + 0.1;
    controls.minDistance = 20;
    controls.maxDistance = 500;
    controlsRef.current = controls;

    // 4. Directional & Ambient Lighting for surface hillshading
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
    scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xfff7e6, 1.25);
    sunLight.position.set(60, -80, 120);
    scene.add(sunLight);

    const fillLight = new THREE.DirectionalLight(0x90b0e0, 0.4);
    fillLight.position.set(-60, 80, -30);
    scene.add(fillLight);

    // 5. Grid Helper (reference ground plane)
    const gridHelper = new THREE.GridHelper(120, 12, 0x1e293b, 0x0f172a);
    gridHelper.rotation.x = Math.PI / 2;
    gridHelper.position.z = -1;
    scene.add(gridHelper);

    // 6. Build Elevation Mesh from REAL depth map
    const segments = 160; // 160x160 grid = 25,600 vertices; lightweight & responsive
    const geomWidth = 100;
    const geomHeight = 100;

    const depthImg = new Image();
    depthImg.crossOrigin = 'anonymous';

    depthImg.onload = () => {
      // Sample elevation values via offscreen canvas
      const canvas = document.createElement('canvas');
      canvas.width = segments + 1;
      canvas.height = segments + 1;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      ctx.drawImage(depthImg, 0, 0, canvas.width, canvas.height);
      const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height).data;

      const vertexCount = (segments + 1) * (segments + 1);
      const baseHeights = new Float32Array(vertexCount);

      // Viridis colormap has low elevation at dark purple and high at bright yellow
      // Compute perceived luminance/brightness [0.0, 1.0] as relative height
      for (let i = 0; i < vertexCount; i++) {
        const r = imgData[i * 4];
        const g = imgData[i * 4 + 1];
        const b = imgData[i * 4 + 2];
        // Standard perceived luminance
        const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0;
        baseHeights[i] = lum;
      }
      baseHeightsRef.current = baseHeights;

      // Create Plane Geometry
      const geometry = new THREE.PlaneGeometry(geomWidth, geomHeight, segments, segments);
      const posAttr = geometry.attributes.position;

      // PlaneGeometry in Three.js has X, Y on plane and Z as normal
      // Apply displacement along Z
      const elevationScale = 22.0; // Base elevation scale
      for (let i = 0; i < posAttr.count; i++) {
        const z = baseHeights[i] * elevationScale * verticalScale;
        posAttr.setZ(i, z);
      }
      geometry.computeVertexNormals();

      // Load optical texture and depth texture
      const texLoader = new THREE.TextureLoader();
      texLoader.load(originalImageUrl, (opticalTex) => {
        opticalTex.colorSpace = THREE.SRGBColorSpace;
        opticalTextureRef.current = opticalTex;

        texLoader.load(fullDepthUrl, (depthTex) => {
          depthTex.colorSpace = THREE.SRGBColorSpace;
          depthTextureRef.current = depthTex;

          const material = new THREE.MeshStandardMaterial({
            map: opticalTex,
            roughness: 0.85,
            metalness: 0.1,
            wireframe: wireframe,
            side: THREE.DoubleSide,
          });

          const mesh = new THREE.Mesh(geometry, material);
          scene.add(mesh);
          meshRef.current = mesh;
          setIsLoadingMesh(false);
        });
      });
    };

    depthImg.src = fullDepthUrl;

    // 7. Render Loop
    const animate = () => {
      animationFrameIdRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // 8. Resize Handler
    const handleResize = () => {
      if (!mountRef.current || !rendererRef.current || !cameraRef.current) return;
      const newWidth = mountRef.current.clientWidth;
      cameraRef.current.aspect = newWidth / height;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(newWidth, height);
    };
    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      if (animationFrameIdRef.current) {
        cancelAnimationFrame(animationFrameIdRef.current);
      }
      if (meshRef.current) {
        meshRef.current.geometry.dispose();
        if (Array.isArray(meshRef.current.material)) {
          meshRef.current.material.forEach((m) => m.dispose());
        } else {
          meshRef.current.material.dispose();
        }
      }
      if (opticalTextureRef.current) opticalTextureRef.current.dispose();
      if (depthTextureRef.current) depthTextureRef.current.dispose();
      controls.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [originalImageUrl, fullDepthUrl]);

  // Handle Vertical Exaggeration Slider changes dynamically
  useEffect(() => {
    if (!meshRef.current || !baseHeightsRef.current) return;
    const geometry = meshRef.current.geometry as THREE.PlaneGeometry;
    const posAttr = geometry.attributes.position;
    const baseHeights = baseHeightsRef.current;
    const elevationScale = 22.0;

    for (let i = 0; i < posAttr.count; i++) {
      const z = baseHeights[i] * elevationScale * verticalScale;
      posAttr.setZ(i, z);
    }
    posAttr.needsUpdate = true;
    geometry.computeVertexNormals();
  }, [verticalScale]);

  // Handle Wireframe Toggle
  useEffect(() => {
    if (!meshRef.current) return;
    const mat = meshRef.current.material as THREE.MeshStandardMaterial;
    mat.wireframe = wireframe;
  }, [wireframe]);

  // Handle Texture Mode Switch
  useEffect(() => {
    if (!meshRef.current) return;
    const mat = meshRef.current.material as THREE.MeshStandardMaterial;

    if (textureMode === 'optical' && opticalTextureRef.current) {
      mat.map = opticalTextureRef.current;
      mat.color.set(0xffffff);
      mat.roughness = 0.85;
    } else if (textureMode === 'depth' && depthTextureRef.current) {
      mat.map = depthTextureRef.current;
      mat.color.set(0xffffff);
      mat.roughness = 0.85;
    } else if (textureMode === 'shaded') {
      mat.map = null;
      mat.color.set(0xa0b4c8);
      mat.roughness = 0.6;
    }
    mat.needsUpdate = true;
  }, [textureMode]);

  const handleResetCamera = () => {
    if (!cameraRef.current || !controlsRef.current) return;
    cameraRef.current.position.set(0, -110, 85);
    cameraRef.current.lookAt(0, 0, 0);
    controlsRef.current.target.set(0, 0, 0);
    controlsRef.current.update();
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
      {/* Top Header & Controls */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-slate-800">
        <div className="flex items-center space-x-2">
          <Box className="w-4 h-4 text-cyan-400" />
          <h2 className="text-sm font-semibold text-white">3D Terrain Mesh Viewer</h2>
          <span className="text-[11px] font-mono text-cyan-300 bg-cyan-950/80 px-2 py-0.5 rounded border border-cyan-800/60">
            {depthType}
          </span>
        </div>

        {/* View / Texture Controls */}
        <div className="flex items-center space-x-2">
          <div className="flex items-center bg-slate-950/80 p-1 rounded-lg border border-slate-800 text-xs">
            <button
              onClick={() => setTextureMode('optical')}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                textureMode === 'optical' ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Optical Texture
            </button>
            <button
              onClick={() => setTextureMode('depth')}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                textureMode === 'depth' ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Viridis Colormap
            </button>
            <button
              onClick={() => setTextureMode('shaded')}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                textureMode === 'shaded' ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Hillshade Relief
            </button>
          </div>

          <button
            onClick={() => setWireframe(!wireframe)}
            className={`px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors ${
              wireframe
                ? 'bg-cyan-950 text-cyan-300 border-cyan-700'
                : 'bg-slate-950/80 text-slate-400 border-slate-800 hover:text-slate-200'
            }`}
          >
            Wireframe
          </button>

          <button
            onClick={handleResetCamera}
            title="Reset Camera View"
            className="p-1.5 bg-slate-950/80 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 rounded-lg transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Vertical Exaggeration Slider */}
      <div className="flex items-center space-x-4 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 text-xs text-slate-300">
        <span className="text-slate-400 font-mono flex items-center space-x-1">
          <Sliders className="w-3.5 h-3.5 text-cyan-400" />
          <span>Vertical Exaggeration:</span>
        </span>
        <input
          type="range"
          min="0.1"
          max="3.0"
          step="0.1"
          value={verticalScale}
          onChange={(e) => setVerticalScale(parseFloat(e.target.value))}
          className="flex-1 accent-cyan-500 cursor-pointer"
        />
        <span className="font-mono text-cyan-300 w-12 text-right">{verticalScale.toFixed(1)}&times;</span>
      </div>

      {/* WebGL Canvas Container */}
      <div className="relative rounded-xl overflow-hidden border border-slate-800 bg-slate-950 shadow-inner">
        {isLoadingMesh && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-slate-950/90 text-cyan-300 space-y-2">
            <Box className="w-8 h-8 animate-bounce text-cyan-400" />
            <span className="text-xs font-mono">Displacing 3D vertices from predicted relief...</span>
          </div>
        )}

        <div ref={mountRef} className="w-full h-[480px] cursor-grab active:cursor-grabbing" />

        {/* 3D Navigation Guide Overlay */}
        <div className="absolute bottom-3 left-3 bg-slate-950/85 backdrop-blur-sm border border-slate-800 px-3 py-2 rounded-lg text-[11px] text-slate-400 space-y-0.5 pointer-events-none">
          <div className="text-slate-300 font-semibold mb-1">Interactive 3D Navigation</div>
          <div>&bull; Left Drag: Orbit / Rotate scene</div>
          <div>&bull; Right Drag: Pan camera</div>
          <div>&bull; Scroll: Zoom in / out</div>
        </div>

        {/* Scientific Rule §7 Badge */}
        <div className="absolute top-3 right-3 bg-slate-950/85 backdrop-blur-sm border border-slate-800 px-2.5 py-1.5 rounded-lg text-[10px] text-slate-300 font-mono space-y-0.5 pointer-events-none">
          <div>Grid: 160 &times; 160 vertices (25,600 nodes)</div>
          <div className="text-cyan-400">Vertex Displacement: Real ONNX Depth</div>
          <div className={isMetric ? "text-emerald-400" : "text-amber-400"}>
            Surface: {isMetric ? "Calibrated Metric (m)" : "Unitless Disparity"}
          </div>
        </div>
      </div>
    </div>
  );
};
