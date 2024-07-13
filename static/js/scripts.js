/*!
* Start Bootstrap - Grayscale v7.0.6 (https://startbootstrap.com/theme/grayscale)
* Copyright 2013-2023 Start Bootstrap
* Licensed under MIT (https://github.com/StartBootstrap/startbootstrap-grayscale/blob/master/LICENSE)
*/
//
// Scripts
// 

window.addEventListener('DOMContentLoaded', event => {

    // Navbar shrink function
    var navbarShrink = function () {
        const navbarCollapsible = document.body.querySelector('#mainNav');
        if (!navbarCollapsible) {
            return;
        }
        if (window.scrollY === 0) {
            navbarCollapsible.classList.remove('navbar-shrink')
        } else {
            navbarCollapsible.classList.add('navbar-shrink')
        }

    };

    // Shrink the navbar 
    navbarShrink();

    // Shrink the navbar when page is scrolled
    document.addEventListener('scroll', navbarShrink);

    // Activate Bootstrap scrollspy on the main nav element
    const mainNav = document.body.querySelector('#mainNav');
    if (mainNav) {
        new bootstrap.ScrollSpy(document.body, {
            target: '#mainNav',
            rootMargin: '0px 0px -40%',
        });
    };

    // Collapse responsive navbar when toggler is visible
    const navbarToggler = document.body.querySelector('.navbar-toggler');
    const responsiveNavItems = [].slice.call(
        document.querySelectorAll('#navbarResponsive .nav-link')
    );
    responsiveNavItems.map(function (responsiveNavItem) {
        responsiveNavItem.addEventListener('click', () => {
            if (window.getComputedStyle(navbarToggler).display !== 'none') {
                navbarToggler.click();
            }
        });
    });

    // Function to update <p> tags with class "timestamp"
    const updateTimestamps = () => {
        const timestampElements = document.querySelectorAll('p.timestamp');
        timestampElements.forEach(element => {
            try {
                const formattedDate = formatTimestamp(element.id);
                element.textContent = formattedDate;
            } catch (error) {
                console.error(`Error formatting timestamp for element with id ${element.id}:`, error);
            }
        });
    };

    // Update timestamps on DOM content loaded
    updateTimestamps();
});

function formatTimestamp(filename) {
    // Regular expression to match the timestamp in the filename
    const regex = /_(\d{14})_/;
    const match = filename.match(regex);

    if (!match) {
        throw new Error("Timestamp not found in the filename");
    }

    const timestamp = match[1];

    // Parse the timestamp into a Date object
    const year = timestamp.substring(0, 4);
    const month = timestamp.substring(4, 6) - 1; // Months are 0-based in JavaScript
    const day = timestamp.substring(6, 8);
    const hours = timestamp.substring(8, 10);
    const minutes = timestamp.substring(10, 12);
    const seconds = timestamp.substring(12, 14);

    const date = new Date(year, month, day, hours, minutes, seconds);

    // Format the Date object into 'dd-MMM-yyyy hh:mm:ss'
    const options = { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
    const formattedDate = date.toLocaleString('en-US', options).replace(',', '');

    return formattedDate;
}