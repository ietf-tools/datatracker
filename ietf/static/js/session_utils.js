// Copyright The IETF Trust 2025, All Rights Reserved

document.addEventListener('DOMContentLoaded', () => {
    // add stripes
    const firstRow = document.querySelector('.custom-stripe .row')
    if (firstRow) {
        const parent = firstRow.parentElement;
        const allRows = Array.from(parent.children).filter(child => child.classList.contains('row'))
        allRows.forEach((row, index) => {
            row.classList.remove('bg-light')
            if (index % 2 === 1) {
                row.classList.add('bg-light')
            }
        })
    }
})
