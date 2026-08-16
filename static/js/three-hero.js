// Subtle animated 3D backdrop for the landing hero — a drifting particle
// network plus a slowly-rotating wireframe icosahedron ("data node" motif).
// Degrades silently if Three.js/WebGL isn't available.
(function () {
  document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("hero-3d");
    if (!container || typeof THREE === "undefined") return;

    let width = container.clientWidth;
    let height = container.clientHeight;

    const isDark = document.documentElement.classList.contains("dark");
    const particleColor = isDark ? 0x818cf8 : 0x6366f1;
    const lineColor = isDark ? 0x6366f1 : 0xa5b4fc;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 1000);
    camera.position.set(0, 0, 40);

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    } catch (e) {
      return; // no WebGL support — fail quietly
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    container.appendChild(renderer.domElement);

    // --- Particle network ------------------------------------------------
    const COUNT = 70;
    const RANGE = 26;
    const positions = new Float32Array(COUNT * 3);
    const velocities = [];

    for (let i = 0; i < COUNT; i++) {
      positions[i * 3] = (Math.random() - 0.5) * RANGE * 2;
      positions[i * 3 + 1] = (Math.random() - 0.5) * RANGE * 2;
      positions[i * 3 + 2] = (Math.random() - 0.5) * RANGE;
      velocities.push({
        x: (Math.random() - 0.5) * 0.02,
        y: (Math.random() - 0.5) * 0.02,
        z: (Math.random() - 0.5) * 0.02,
      });
    }

    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const particleMaterial = new THREE.PointsMaterial({
      color: particleColor,
      size: 0.55,
      transparent: true,
      opacity: 0.85,
    });
    const points = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(points);

    const lineGeometry = new THREE.BufferGeometry();
    const lineMaterial = new THREE.LineBasicMaterial({
      color: lineColor,
      transparent: true,
      opacity: 0.18,
    });
    const lines = new THREE.LineSegments(lineGeometry, lineMaterial);
    scene.add(lines);

    const LINK_DISTANCE = 9;

    function updateLinks() {
      const pos = particleGeometry.attributes.position.array;
      const linePositions = [];
      for (let i = 0; i < COUNT; i++) {
        for (let j = i + 1; j < COUNT; j++) {
          const dx = pos[i * 3] - pos[j * 3];
          const dy = pos[i * 3 + 1] - pos[j * 3 + 1];
          const dz = pos[i * 3 + 2] - pos[j * 3 + 2];
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
          if (dist < LINK_DISTANCE) {
            linePositions.push(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);
            linePositions.push(pos[j * 3], pos[j * 3 + 1], pos[j * 3 + 2]);
          }
        }
      }
      lineGeometry.setAttribute("position", new THREE.Float32BufferAttribute(linePositions, 3));
    }

    // --- Centerpiece wireframe icosahedron --------------------------------
    const icoGeometry = new THREE.IcosahedronGeometry(9, 1);
    const icoMaterial = new THREE.MeshBasicMaterial({
      color: particleColor,
      wireframe: true,
      transparent: true,
      opacity: 0.35,
    });
    const ico = new THREE.Mesh(icoGeometry, icoMaterial);
    scene.add(ico);

    // --- Mouse parallax -----------------------------------------------------
    let mouseX = 0;
    let mouseY = 0;
    window.addEventListener("mousemove", (e) => {
      mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
      mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
    });

    function resize() {
      width = container.clientWidth;
      height = container.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    }
    window.addEventListener("resize", resize);

    let frame = 0;
    function animate() {
      frame += 1;
      const pos = particleGeometry.attributes.position.array;
      for (let i = 0; i < COUNT; i++) {
        pos[i * 3] += velocities[i].x;
        pos[i * 3 + 1] += velocities[i].y;
        pos[i * 3 + 2] += velocities[i].z;

        if (Math.abs(pos[i * 3]) > RANGE) velocities[i].x *= -1;
        if (Math.abs(pos[i * 3 + 1]) > RANGE) velocities[i].y *= -1;
        if (Math.abs(pos[i * 3 + 2]) > RANGE / 2) velocities[i].z *= -1;
      }
      particleGeometry.attributes.position.needsUpdate = true;
      if (frame % 3 === 0) updateLinks();

      ico.rotation.x += 0.0015;
      ico.rotation.y += 0.0022;

      camera.position.x += (mouseX * 6 - camera.position.x) * 0.02;
      camera.position.y += (-mouseY * 6 - camera.position.y) * 0.02;
      camera.lookAt(scene.position);

      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    }
    animate();
  });
})();
