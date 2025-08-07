const toc = document.getElementById("toc");
toc.querySelector("h2").addEventListener("click", e => {
  toc.classList.toggle("active");
});
toc.querySelector("nav").addEventListener("click", e => {
  toc.classList.remove("active");
});
