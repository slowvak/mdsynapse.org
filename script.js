// ==========================================
// NEURAL NETWORK CANVAS ANIMATION
// ==========================================

class NeuralNetwork {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.nodes = [];
        this.connections = [];
        this.mousePosition = { x: 0, y: 0 };

        this.resize();
        this.init();
        this.animate();

        window.addEventListener('resize', () => this.resize());
        canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
    }

    resize() {
        this.canvas.width = this.canvas.offsetWidth;
        this.canvas.height = this.canvas.offsetHeight;
    }

    init() {
        const nodeCount = Math.floor((this.canvas.width * this.canvas.height) / 15000);
        this.nodes = [];

        for (let i = 0; i < nodeCount; i++) {
            this.nodes.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                radius: Math.random() * 2 + 1
            });
        }
    }

    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        this.mousePosition.x = e.clientX - rect.left;
        this.mousePosition.y = e.clientY - rect.top;
    }

    updateNodes() {
        this.nodes.forEach(node => {
            // Move nodes
            node.x += node.vx;
            node.y += node.vy;

            // Bounce off edges
            if (node.x < 0 || node.x > this.canvas.width) node.vx *= -1;
            if (node.y < 0 || node.y > this.canvas.height) node.vy *= -1;

            // Mouse interaction
            const dx = this.mousePosition.x - node.x;
            const dy = this.mousePosition.y - node.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < 150) {
                const force = (150 - distance) / 150;
                node.x -= dx * force * 0.02;
                node.y -= dy * force * 0.02;
            }
        });
    }

    drawNodes() {
        this.nodes.forEach((node, i) => {
            this.ctx.beginPath();
            this.ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            // Alternate between purple and cyan nodes for variety
            const colors = [
                'rgba(139, 92, 246, 0.7)',  // Purple
                'rgba(6, 182, 212, 0.7)',   // Cyan
                'rgba(244, 63, 94, 0.5)'    // Coral accent
            ];
            this.ctx.fillStyle = colors[i % colors.length];
            this.ctx.fill();

            // Add glow effect
            this.ctx.shadowBlur = 8;
            this.ctx.shadowColor = colors[i % colors.length];
            this.ctx.fill();
            this.ctx.shadowBlur = 0;
        });
    }

    drawConnections() {
        this.nodes.forEach((node, i) => {
            this.nodes.slice(i + 1).forEach(otherNode => {
                const dx = node.x - otherNode.x;
                const dy = node.y - otherNode.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < 150) {
                    this.ctx.beginPath();
                    this.ctx.moveTo(node.x, node.y);
                    this.ctx.lineTo(otherNode.x, otherNode.y);
                    const opacity = (1 - distance / 150) * 0.4;
                    // Create gradient for connections
                    const gradient = this.ctx.createLinearGradient(node.x, node.y, otherNode.x, otherNode.y);
                    gradient.addColorStop(0, `rgba(139, 92, 246, ${opacity})`);
                    gradient.addColorStop(1, `rgba(6, 182, 212, ${opacity})`);
                    this.ctx.strokeStyle = gradient;
                    this.ctx.lineWidth = 1;
                    this.ctx.stroke();
                }
            });
        });
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.updateNodes();
        this.drawConnections();
        this.drawNodes();
        requestAnimationFrame(() => this.animate());
    }
}

// Initialize neural network when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('neural-canvas');
    if (canvas) {
        new NeuralNetwork(canvas);
    }
});

// ==========================================
// SMOOTH SCROLL FOR NAVIGATION LINKS
// ==========================================

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const targetId = this.getAttribute('href');
        if (targetId === '#') return;

        const targetElement = document.querySelector(targetId);
        if (targetElement) {
            const navHeight = document.querySelector('.nav').offsetHeight;
            const targetPosition = targetElement.offsetTop - navHeight;

            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });
        }
    });
});

// ==========================================
// NAVBAR SCROLL EFFECT
// ==========================================

let lastScroll = 0;
const nav = document.querySelector('.nav');

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;

    if (currentScroll > 100) {
        nav.style.background = 'rgba(30, 27, 75, 0.85)';
        nav.style.backdropFilter = 'blur(20px) saturate(180%)';
        nav.style.boxShadow = '0 4px 20px rgba(139, 92, 246, 0.15)';
    } else {
        nav.style.background = 'rgba(30, 27, 75, 0.6)';
        nav.style.backdropFilter = 'blur(16px) saturate(180%)';
        nav.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.05)';
    }

    lastScroll = currentScroll;
});

// ==========================================
// INTERSECTION OBSERVER FOR ANIMATIONS
// ==========================================

const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe elements for fade-in animation
document.addEventListener('DOMContentLoaded', () => {
    const animatedElements = document.querySelectorAll(
        '.pillar-card, .article-card, .about-content, .manifesto-quote'
    );

    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
});

// ==========================================
// NEWSLETTER FORM HANDLING
// ==========================================

const newsletterForm = document.querySelector('.newsletter-form');
if (newsletterForm) {
    newsletterForm.addEventListener('submit', (e) => {
        e.preventDefault();

        const emailInput = newsletterForm.querySelector('.newsletter-input');
        const email = emailInput.value;

        // Basic email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        if (emailRegex.test(email)) {
            // Success feedback
            const button = newsletterForm.querySelector('.btn');
            const originalText = button.textContent;

            button.textContent = 'Thank you!';
            button.style.background = 'linear-gradient(135deg, #8B5CF6, #06B6D4)';
            emailInput.value = '';

            // Reset after 3 seconds
            setTimeout(() => {
                button.textContent = originalText;
                button.style.background = '';
            }, 3000);

            // Here you would typically send the email to your backend
            console.log('Newsletter subscription:', email);

            // Example: Send to backend
            // fetch('/api/subscribe', {
            //     method: 'POST',
            //     headers: { 'Content-Type': 'application/json' },
            //     body: JSON.stringify({ email })
            // });

        } else {
            // Error feedback
            emailInput.style.borderColor = '#EF4444';
            emailInput.placeholder = 'Please enter a valid email';

            setTimeout(() => {
                emailInput.style.borderColor = '';
                emailInput.placeholder = 'your.email@example.com';
            }, 2000);
        }
    });
}

// ==========================================
// ARTICLE CARD HOVER EFFECT
// ==========================================

document.querySelectorAll('.article-card').forEach(card => {
    card.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-8px)';
    });

    card.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
    });
});

// ==========================================
// PERFORMANCE: REDUCE MOTION FOR USERS WHO PREFER IT
// ==========================================

const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

if (prefersReducedMotion.matches) {
    // Disable animations for users who prefer reduced motion
    document.querySelectorAll('*').forEach(el => {
        el.style.animation = 'none';
        el.style.transition = 'none';
    });
}

// ==========================================
// MOBILE MENU TOGGLE (For future implementation)
// ==========================================

// Add hamburger menu for mobile if needed
function createMobileMenu() {
    const nav = document.querySelector('.nav-content');
    const navLinks = document.querySelector('.nav-links');

    // Check if screen is mobile
    if (window.innerWidth <= 768) {
        // Create hamburger button if it doesn't exist
        if (!document.querySelector('.mobile-menu-toggle')) {
            const toggleButton = document.createElement('button');
            toggleButton.className = 'mobile-menu-toggle';
            toggleButton.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <line x1="3" y1="12" x2="21" y2="12" stroke-width="2"/>
                    <line x1="3" y1="6" x2="21" y2="6" stroke-width="2"/>
                    <line x1="3" y1="18" x2="21" y2="18" stroke-width="2"/>
                </svg>
            `;
            toggleButton.style.cssText = `
                background: none;
                border: none;
                color: #06B6D4;
                cursor: pointer;
                padding: 0.5rem;
                display: flex;
                align-items: center;
                justify-content: center;
            `;

            nav.appendChild(toggleButton);

            toggleButton.addEventListener('click', () => {
                navLinks.classList.toggle('active');
            });
        }
    }
}

window.addEventListener('resize', createMobileMenu);
createMobileMenu();

// ==========================================
// LOADING ANIMATION
// ==========================================

window.addEventListener('load', () => {
    document.body.style.opacity = '0';
    setTimeout(() => {
        document.body.style.transition = 'opacity 0.5s ease';
        document.body.style.opacity = '1';
    }, 100);
});

// ==========================================
// ARTICLE SHARE BUTTONS
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    const shareButtons = document.querySelectorAll('.share-btn');
    
    shareButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            
            const url = window.location.href;
            const title = document.title;
            const type = button.getAttribute('aria-label');
            
            if (type === 'Share on Twitter') {
                window.open(`https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(title)}`, '_blank');
            } else if (type === 'Share on LinkedIn') {
                window.open(`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`, '_blank');
            } else if (type === 'Copy link') {
                navigator.clipboard.writeText(url).then(() => {
                    const originalText = button.textContent;
                    button.textContent = 'Copied!';
                    button.style.background = 'var(--teal-primary)';
                    button.style.color = 'var(--white-neural)';
                    
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.style.background = '';
                        button.style.color = '';
                    }, 2000);
                });
            }
        });
    });
});

// ==========================================
// BACK TO TOP BUTTON
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    const backToTop = document.createElement('a');
    backToTop.href = '#';
    backToTop.innerHTML = '↑';
    backToTop.setAttribute('aria-label', 'Back to top');
    backToTop.style.cssText = [
        'position: fixed',
        'bottom: 2rem',
        'right: 2rem',
        'width: 44px',
        'height: 44px',
        'background: linear-gradient(135deg, #8B5CF6 0%, #06B6D4 100%)',
        'color: white',
        'border-radius: 50%',
        'display: flex',
        'align-items: center',
        'justify-content: center',
        'opacity: 0',
        'transition: opacity 0.3s, transform 0.3s',
        'z-index: 999',
        'cursor: pointer',
        'text-decoration: none',
        'font-size: 1.25rem',
        'font-weight: bold',
        'box-shadow: 0 4px 12px rgba(139, 92, 246, 0.4)',
        'pointer-events: none',
    ].join('; ');
    document.body.appendChild(backToTop);

    window.addEventListener('scroll', () => {
        if (window.scrollY > 400) {
            backToTop.style.opacity = '0.85';
            backToTop.style.transform = 'translateY(0)';
            backToTop.style.pointerEvents = 'auto';
        } else {
            backToTop.style.opacity = '0';
            backToTop.style.transform = 'translateY(8px)';
            backToTop.style.pointerEvents = 'none';
        }
    });
});

// ==========================================
// CONSOLE EASTER EGG
// ==========================================

console.log('%c🧠 MDSynapse.org', 'color: #8B5CF6; font-size: 24px; font-weight: bold;');
console.log('%cThink deep. Know more. Heal well.', 'color: #06B6D4; font-size: 14px;');
console.log('%cInterested in the code? Check out the repo!', 'color: #1E1B4B; font-size: 12px;');
