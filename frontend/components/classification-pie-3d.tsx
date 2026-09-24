'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';

type Slice = { label: string; value: number; color: string };
const palette = ['#e14b45', '#2aa77b', '#77899c', '#2577d4', '#ef8b25', '#e3b52b', '#13a8b8', '#8667dd', '#d66eac'];

export default function ClassificationPie3D({ classification, rules, counts, compact = false, fullScreen = false, sectionHeader }: {
  classification: { sif: number; non_sif: number; unresolved: number };
  rules: string[]; counts: number[][]; compact?: boolean; fullScreen?: boolean; sectionHeader?: React.ReactNode;
}) {
  const [view, setView] = useState<'classification' | 'rules'>('classification');
  const [hovered, setHovered] = useState<{ label: string; value: number; color: string; percent: number } | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const mount = useRef<HTMLDivElement>(null);
  const lastHoveredRef = useRef<string | null>(null);

  const classificationSlices = useMemo<Slice[]>(() => [
    { label: 'SIF-potential', value: classification.sif, color: palette[0] },
    { label: 'Non-SIF', value: classification.non_sif, color: palette[1] },
    { label: 'Unresolved', value: classification.unresolved, color: palette[2] },
  ].filter(d => d.value > 0), [classification]);

  const ruleSlices = useMemo<Slice[]>(() => rules.map((label, i) => ({
    label, value: counts.reduce((total, row) => total + row[i], 0), color: palette[(i + 3) % palette.length],
  })).filter(d => d.value > 0), [rules, counts]);

  const slices = view === 'classification' ? classificationSlices : ruleSlices;
  const total = slices.reduce((sum, item) => sum + item.value, 0);

  useEffect(() => {
    const host = mount.current;
    if (!host || !total) return;
    const width = Math.max(host.clientWidth || 0, 180);
    const height = Math.max(host.clientHeight || 0, fullScreen ? 580 : 180);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 100);
    if (fullScreen) {
      camera.position.set(0, 3.4, 4.6);
      camera.lookAt(0, 0.04, 0);
    } else {
      // Zoomed in just a little: full, clear presence with safe padding from card boundaries
      camera.position.set(0, 3.38, 4.52);
      camera.lookAt(0, 0.04, 0);
    }

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.domElement.setAttribute('aria-hidden', 'true');
    host.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 1.6));
    const light = new THREE.DirectionalLight(0xffffff, 2.5);
    light.position.set(4, 6, 3);
    scene.add(light);

    const group = new THREE.Group();
    group.position.y = 0.01;
    scene.add(group);

    const meshes: THREE.Mesh[] = [];
    let angle = Math.PI / 2;
    for (const item of slices) {
      const sweep = (item.value / total) * Math.PI * 2;
      const shape = new THREE.Shape();
      const segments = 48;
      const inner = 0.52;
      const outer = 1.20;
      shape.moveTo(outer * Math.cos(angle), outer * Math.sin(angle));
      for (let i = 1; i <= segments; i++) {
        const a = angle + (sweep * i) / segments;
        shape.lineTo(outer * Math.cos(a), outer * Math.sin(a));
      }
      for (let i = segments; i >= 0; i--) {
        const a = angle + (sweep * i) / segments;
        shape.lineTo(inner * Math.cos(a), inner * Math.sin(a));
      }
      const geometry = new THREE.ExtrudeGeometry(shape, {
        depth: 0.24,
        bevelEnabled: true,
        bevelThickness: 0.018,
        bevelSize: 0.012,
        bevelSegments: 2,
      });
      geometry.rotateX(-Math.PI / 2);
      const mesh = new THREE.Mesh(
        geometry,
        new THREE.MeshPhongMaterial({ color: item.color, shininess: 70 })
      );
      mesh.userData = item;
      group.add(mesh);
      meshes.push(mesh);
      angle += sweep;
    }

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2(-10, -10);

    const move = (event: PointerEvent) => {
      const box = renderer.domElement.getBoundingClientRect();
      const x = event.clientX - box.left;
      const y = event.clientY - box.top;
      pointer.set((x / box.width) * 2 - 1, -(y / box.height) * 2 + 1);
      setMousePos({ x, y });
    };

    const leave = () => {
      pointer.set(-10, -10);
      lastHoveredRef.current = null;
      setHovered(null);
    };

    renderer.domElement.addEventListener('pointermove', move);
    renderer.domElement.addEventListener('pointerleave', leave);

    let frame = 0;
    const draw = () => {
      frame = requestAnimationFrame(draw);
      raycaster.setFromCamera(pointer, camera);
      const intersects = raycaster.intersectObjects(meshes);
      const hit = intersects[0]?.object as THREE.Mesh | undefined;

      for (const mesh of meshes) {
        const active = mesh === hit;
        mesh.position.y += ((active ? 0.08 : 0) - mesh.position.y) * 0.15;
        mesh.scale.y += ((active ? 1.10 : 1) - mesh.scale.y) * 0.15;
      }

      if (hit && hit.userData) {
        const item = hit.userData as Slice;
        if (lastHoveredRef.current !== item.label) {
          lastHoveredRef.current = item.label;
          const pct = Math.round((item.value / total) * 100);
          setHovered({
            label: item.label,
            value: item.value,
            color: item.color,
            percent: pct,
          });
        }
      } else if (lastHoveredRef.current !== null) {
        lastHoveredRef.current = null;
        setHovered(null);
      }

      renderer.render(scene, camera);
    };
    draw();

    const resize = new ResizeObserver(() => {
      const w = Math.max(host.clientWidth || 0, 180);
      const h = Math.max(host.clientHeight || 0, fullScreen ? 600 : 180);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    resize.observe(host);

    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      renderer.domElement.removeEventListener('pointermove', move);
      renderer.domElement.removeEventListener('pointerleave', leave);
      meshes.forEach((mesh) => {
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      });
      renderer.dispose();
      host.replaceChildren();
    };
  }, [slices, total, compact, fullScreen]);

  return (
    <section
      className={'oil-panel classification-3d ' + (compact ? 'compact ' : '') + (fullScreen ? 'fullscreen' : '')}
      style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}
    >
      {sectionHeader ? (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {sectionHeader}
          <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '4px 10px', background: '#fcfdfe', borderBottom: '1px solid #edf3fa' }}>
            <div className="chart-toggle" aria-label="Classification chart measure" style={{ margin: 0 }}>
              <button type="button" aria-pressed={view === 'classification'} onClick={() => setView('classification')}>
                SIF classification
              </button>
              <button type="button" aria-pressed={view === 'rules'} onClick={() => setView('rules')}>
                Life-saving rules
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="panel-head chart-heading">
          <div>
            <p className="eyebrow">CLASSIFICATION VIEW</p>
            <h2>Assessment mix</h2>
          </div>
          <div className="chart-toggle" aria-label="Classification chart measure">
            <button type="button" aria-pressed={view === 'classification'} onClick={() => setView('classification')}>
              SIF classification
            </button>
            <button type="button" aria-pressed={view === 'rules'} onClick={() => setView('rules')}>
              Life-saving rules
            </button>
          </div>
        </div>
      )}
      <div className="pie-3d-body" style={{ display: 'flex', flexDirection: 'column', flex: '1 1 auto', width: '100%', height: '100%', minHeight: 0, position: 'relative' }}>
        <div className="pie-3d-canvas" style={{ flex: '1 1 auto', width: '100%', height: '100%', minHeight: 0, position: 'relative' }}>
          <div className="pie-3d-mount" ref={mount} style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }} />

          {/* Floating Hover Tooltip directly over hovered slice */}
          {hovered && (
            <div
              className="pie-3d-tooltip"
              style={{
                left: Math.min(Math.max(mousePos.x, 75), (mount.current?.clientWidth || 280) - 75),
                top: Math.max(mousePos.y - 12, 10),
                transform: 'translate(-50%, -100%)',
              }}
            >
              <div className="pie-tooltip-card">
                <div className="pie-tooltip-header">
                  <span className="pie-tooltip-dot" style={{ background: hovered.color }} />
                  <span className="pie-tooltip-label">{hovered.label}</span>
                </div>
                <div className="pie-tooltip-value">
                  <strong style={{ color: hovered.color }}>{hovered.percent}%</strong>
                  <span className="pie-tooltip-count">({hovered.value} reports)</span>
                </div>
              </div>
            </div>
          )}

          {/* Constant Center Donut Label positioned cleanly in optical center */}
          <div className="pie-3d-center-overlay" style={{ top: '43.5%' }}>
            <strong style={{ display: 'block', fontSize: fullScreen ? '28px' : '18px', fontWeight: 800, color: '#0430bd', lineHeight: 1.1 }}>
              {total}
            </strong>
            <span style={{ display: 'block', fontSize: fullScreen ? '11px' : '9.5px', fontWeight: 600, color: '#3b618f', marginTop: '1px' }}>
              Total reports
            </span>
          </div>
        </div>
      </div>
      {!compact && !fullScreen && !sectionHeader && (
        <p className="chart-footnote">
          Unresolved assessments stay separate. Rule totals can exceed report totals because a report can have several tags.
        </p>
      )}
    </section>
  );
}
