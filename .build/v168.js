/* ===== v168 (owner: "make all the page headers orange, eg 'waiver'"). Page titles (.pgtitle h1) in the Pylon accent;
   name headings (.hnm: league/team/player names) and the Huddle greeting keep the text colour. Light mode #BF4706
   (v133 contrast rule). ===== */
document.head.insertAdjacentHTML("beforeend",`<style>
#view .pgtitle h1:not(.hnm):not(.hdh){color:var(--acc)}
:root[data-theme="light"] #view .pgtitle h1:not(.hnm):not(.hdh){color:#BF4706}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]) #view .pgtitle h1:not(.hnm):not(.hdh){color:#BF4706}}
</style>`);
