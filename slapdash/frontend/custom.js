// This is an example of how you may use custom.js to inject additional scripts in the header,
// or to inject additional HTML before or after the webpage.

// var script = document.createElement('script');
// script.type = 'text/javascript';
// script.src = 'http://my-external-script.js';    
// document.head.appendChild(script);

// async function fetchHtmlAsText(url) {
//     return await (await fetch(url)).text();
// }
// async function loadHome() {
//     const contentDiv = document.getElementById("include-before");
//     contentDiv.innerHTML = await fetchHtmlAsText("custom-before.html");
//     const contentDiv2 = document.getElementById("include-after");
//     contentDiv2.innerHTML = await fetchHtmlAsText("custom-after.html");
// }

// window.onload = (event) => loadHome();