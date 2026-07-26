const root = document.documentElement;
const header = document.querySelector(".site-header");
const themeToggle = document.querySelector(".theme-toggle");
const themeColor = document.querySelector('meta[name="theme-color"]');
const menuToggle = document.querySelector(".menu-toggle");
const mobileNav = document.querySelector(".mobile-nav");
const mobileLinks = document.querySelectorAll(".mobile-nav a");
const year = document.querySelector("#year");

const preferredTheme = () => {
  const storedTheme = localStorage.getItem("theme");
  if (storedTheme === "light" || storedTheme === "dark") {
    return storedTheme;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

const setTheme = (theme) => {
  root.dataset.theme = theme;
  localStorage.setItem("theme", theme);

  const isDark = theme === "dark";
  themeToggle.setAttribute("aria-label", `Switch to ${isDark ? "light" : "dark"} theme`);
  themeColor.setAttribute("content", isDark ? "#101815" : "#f4f2eb");
};

setTheme(preferredTheme());

themeToggle.addEventListener("click", () => {
  setTheme(root.dataset.theme === "dark" ? "light" : "dark");
});

const closeMenu = () => {
  menuToggle.setAttribute("aria-expanded", "false");
  menuToggle.setAttribute("aria-label", "Open navigation");
  mobileNav.hidden = true;
  document.body.classList.remove("menu-open");
};

menuToggle.addEventListener("click", () => {
  const isOpen = menuToggle.getAttribute("aria-expanded") === "true";

  if (isOpen) {
    closeMenu();
    return;
  }

  menuToggle.setAttribute("aria-expanded", "true");
  menuToggle.setAttribute("aria-label", "Close navigation");
  mobileNav.hidden = false;
  document.body.classList.add("menu-open");
});

mobileLinks.forEach((link) => link.addEventListener("click", closeMenu));

window.addEventListener("resize", () => {
  if (window.innerWidth > 800 && !mobileNav.hidden) {
    closeMenu();
  }
});

const updateHeader = () => {
  header.classList.toggle("scrolled", window.scrollY > 16);
};

updateHeader();
window.addEventListener("scroll", updateHeader, { passive: true });

const revealElements = document.querySelectorAll(".reveal");

if ("IntersectionObserver" in window) {
  const revealObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }

        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      });
    },
    {
      rootMargin: "0px 0px -8% 0px",
      threshold: 0.08,
    },
  );

  revealElements.forEach((element, index) => {
    element.style.transitionDelay = `${Math.min(index % 4, 3) * 70}ms`;
    revealObserver.observe(element);
  });
} else {
  revealElements.forEach((element) => element.classList.add("visible"));
}

year.textContent = new Date().getFullYear();

const filterButtons = document.querySelectorAll(".filter-button");
const libraryItems = document.querySelectorAll(".library-item");
const libraryCount = document.querySelector(".library-count strong");

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const filter = button.dataset.filter;

    filterButtons.forEach((item) => {
      item.classList.toggle("active", item === button);
      item.setAttribute("aria-pressed", String(item === button));
    });

    let visibleCount = 0;
    libraryItems.forEach((item) => {
      const isVisible = filter === "all" || item.dataset.topic === filter;
      item.hidden = !isVisible;
      visibleCount += Number(isVisible);
    });

    if (libraryCount) {
      libraryCount.textContent = visibleCount;
    }
  });
});

document.querySelectorAll(".copy-citation").forEach((button) => {
  button.addEventListener("click", async () => {
    const code = button.closest(".paper-details-content").querySelector("code");
    const citation = code.textContent.trim();
    const initialLabel = button.textContent;
    let copied = false;

    try {
      await navigator.clipboard.writeText(citation);
      copied = true;
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = citation;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      copied = document.execCommand("copy");
      textarea.remove();
    }

    if (!copied) {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(code);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    button.textContent = copied ? "Copied" : "Selected — press Ctrl+C";

    window.setTimeout(() => {
      button.textContent = initialLabel;
    }, 2200);
  });
});
