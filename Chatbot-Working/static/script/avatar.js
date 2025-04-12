// avatar.js

// Check if avatar.js is loaded
console.log("avatar.js is loaded!");

// Create the scene, camera, and renderer
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// Add orbit controls
const controls = new THREE.OrbitControls(camera, renderer.domElement);

// Load the GLTF model
const loader = new THREE.GLTFLoader();
loader.load('./static/models/avatar/source/avatar.glb', function (gltf) {
    const avatar = gltf.scene;
    scene.add(avatar);
    avatar.position.set(0, -1, 0);  // Adjust position if needed

    // Step 2: Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.5);  // Soft white light
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 2);
    directionalLight.position.set(5, 10, 7.5);
    scene.add(directionalLight);

    animate();
}, undefined, function (error) {
    console.error("Error loading model:", error);
});

// Set camera position
camera.position.set(0, 1, 3);

// Responsive resize
window.addEventListener('resize', () => {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
});

// Animation loop
function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}
