# MDSynapse

**Think deep. Know more. Heal well.**

A modern, responsive website exploring the intersection of medicine, intelligence, and the future clinician.

---

## 🚀 Quick Start

1. Open `MDSynapse.org` in your browser to view the homepage
2. All styling is in `styles.css` and `article-styles.css`
3. Interactive features are in `script.js`

---

## 📁 Project Structure

```
NextGenDoc/
├── index.html              # Main homepage
├── article-template.html   # Blog article template
├── styles.css             # Main stylesheet
├── article-styles.css     # Article-specific styles
├── script.js              # Interactive features & animations
└── README.md              # This file
```

---

## 🎨 Design System

### Color Palette

```css
--navy-dark: #0B1C2D        /* Primary dark background */
--navy-medium: #162B3F      /* Secondary dark */
--teal-primary: #3FD1C1     /* Accent color (your brand) */
--teal-light: #5FDDD0       /* Hover states */
--white-neural: #F5F8FA     /* Light background */
--gray-silver: #AAB4BF      /* Secondary text */
--gray-light: #E1E8ED       /* Borders */
--gray-dark: #657786        /* Body text */
```

### Typography

- **Display/Headings**: Space Grotesk
- **Body**: Inter
- Loaded from Google Fonts

### Logo

The neural cross logo is embedded as inline SVG in both `index.html` and `article-template.html`. The central node pulses using CSS animation.

---
### Interactive Features (`script.js`)

- Neural network canvas animation
- Smooth scroll navigation
- Scroll-based nav styling
- Intersection Observer fade-in animations
- Newsletter form validation
- Responsive mobile menu
- Performance optimizations

---

## 🛠 Customization

### Change Colors

Edit the CSS variables in `styles.css`:

```css
:root {
    --navy-dark: #0B1C2D;
    --teal-primary: #3FD1C1;
    /* etc. */
}
```

### Add New Articles

1. Copy `article-template.html`
2. Rename it (e.g., `my-article.html`)
3. Update the content inside `.article-content`
4. Change the article tag, title, and metadata

### Modify Logo

The logo is an inline SVG. To change it:
1. Find the `.logo-mark` sections in both HTML files
2. Replace the SVG code
3. Or export a new SVG from Figma/Illustrator

### Newsletter Integration

The newsletter form currently logs to console. To connect to a service:

1. Edit `script.js` around line 160
2. Replace the `console.log()` with your API call:

```javascript
fetch('/api/subscribe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
});
```

Popular options:
- Mailchimp
- ConvertKit
- Substack
- Buttondown

---

## 📱 Responsive Design

The site is fully responsive with breakpoints at:
- **768px**: Tablet (nav simplifies, grid adjusts)
- **480px**: Mobile (single column, reduced spacing)

---

## 🚢 Deployment

- **GitHub Pages**: Push to `gh-pages` branch


## 📝 Content Strategy

### Article Tags

Current tags with colors:
- **AI** (teal): Machine learning, algorithms, tech
- **Clinical** (blue): Patient care, diagnosis, treatment
- **Future** (orange): Emerging trends, predictions
- **Ethics** (purple): Moral considerations, philosophy

Add more in `styles.css` under `.tag-*` classes.

### Writing Tips

The design works best with:
- **Clear, bold headlines** (Space Grotesk handles this well)
- **Scannable content** (use subheadings liberally)
- **Thoughtful blockquotes** (they stand out visually)
- **Specific examples** (callout boxes highlight these)

---

## 🎯 SEO & Performance

### Already Implemented

- Semantic HTML5 elements
- Meta descriptions
- Fast loading (no frameworks)
- Responsive images
- Accessible navigation

### To Add

1. **Favicon**: Create `favicon.ico` and add to `<head>`
2. **Open Graph tags**: For social sharing
3. **Analytics**: Add Google Analytics or Plausible
4. **Sitemap**: Create `sitemap.xml` for search engines

---

## 🔧 Future Enhancements

### Recommended Next Steps

1. **Blog System**
   - Use a static site generator (Hugo, Jekyll, 11ty)
   - Or a headless CMS (Contentful, Sanity)

2. **Search Functionality**
   - Implement Algolia or Lunr.js

3. **Comments**
   - Add Disqus, Commento, or Utterances

4. **Dark Mode Toggle**
   - Implement theme switcher (CSS variables make this easy)

5. **Article Series**
   - Add navigation between related articles

---

## 🐛 Browser Support

Tested and works in:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

---

## 📄 License

This template is yours to use freely. No attribution required.

---

## 🤝 Need Help?

Common questions:

**Q: How do I change fonts?**
A: Edit the Google Fonts link in `<head>` and update the CSS variables.

**Q: Can I add a blog?**
A: Yes! Either duplicate `article-template.html` or integrate a static site generator.

**Q: How do I make the logo a file instead of inline SVG?**
A: Export your logo as SVG, save it as `logo.svg`, and replace the SVG code with `<img src="logo.svg" alt="NeoSynapse">`.

**Q: Is this production-ready?**
A: Yes! Just add your content, test on multiple devices, and deploy.

---

**Built with intention. Designed for thinking.**

*— MDSynapse.org*
