// Scene Setup
const scene = new THREE.Scene();

// Camera
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 5, 10); // Adjusted for top-down view
camera.lookAt(0, 0, 0);

// Renderer
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth * 0.8, 400);
document.getElementById("3d-parking").appendChild(renderer.domElement);

// Lighting
const light = new THREE.AmbientLight(0xffffff, 1);
scene.add(light);

// Function to create a car
function createCar(x, z, color) {
    const carGeometry = new THREE.BoxGeometry(1.5, 0.6, 3); // Car size
    const carMaterial = new THREE.MeshStandardMaterial({ color: color });
    const car = new THREE.Mesh(carGeometry, carMaterial);
    car.position.set(x, 0.3, z);
    scene.add(car);
}

// Generate multiple cars (like parking slots)
const carColors = [0xff0000, 0x00ff00, 0x0000ff, 0xffff00, 0xff00ff];
for (let i = -4; i <= 4; i += 2) {
    for (let j = -4; j <= 4; j += 4) {
        createCar(i, j, carColors[Math.floor(Math.random() * carColors.length)]);
    }
}

// Background Color (Parking Lot Look)
scene.background = new THREE.Color(0x222222); // Dark Grey

// Animation Loop
function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}
animate();

// Responsive Design
window.addEventListener('resize', () => {
    renderer.setSize(window.innerWidth * 0.8, 400);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
});
