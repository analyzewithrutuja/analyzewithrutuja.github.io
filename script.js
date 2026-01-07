const imgNeutral = document.getElementById("imgNeutral");
const imgBusiness = document.getElementById("imgBusiness");
const imgEngineer = document.getElementById("imgEngineer");

const bgLeft = document.querySelector(".bg-left");
const bgRight = document.querySelector(".bg-right");

function showImage(activeImg) {
    [imgNeutral, imgBusiness, imgEngineer].forEach(img => {
        img.classList.remove("active");
    });
    activeImg.classList.add("active");
}

function hoverLeft() {
    showImage(imgBusiness);
    bgLeft.style.width = "60%";
    bgRight.style.width = "40%";
}

function hoverRight() {
    showImage(imgEngineer);
    bgLeft.style.width = "40%";
    bgRight.style.width = "60%";
}

function hoverNeutral() {
    showImage(imgNeutral);
    bgLeft.style.width = "50%";
    bgRight.style.width = "50%";
}
