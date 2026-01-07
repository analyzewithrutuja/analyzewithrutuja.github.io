function showNeutral() {
    document.getElementById("imgNeutral").classList.add("active");
    document.getElementById("imgBusiness").classList.remove("active");
    document.getElementById("imgEngineer").classList.remove("active");
}

function showBusiness() {
    document.getElementById("imgNeutral").classList.remove("active");
    document.getElementById("imgBusiness").classList.add("active");
    document.getElementById("imgEngineer").classList.remove("active");
}

function showEngineer() {
    document.getElementById("imgNeutral").classList.remove("active");
    document.getElementById("imgBusiness").classList.remove("active");
    document.getElementById("imgEngineer").classList.add("active");
}


function hoverLeft() {
    document.querySelector(".bg-left").style.width = "60%";
    document.querySelector(".bg-right").style.width = "40%";
    showBusiness();
}

function hoverRight() {
    document.querySelector(".bg-right").style.width = "60%";
    document.querySelector(".bg-left").style.width = "40%";
    showEngineer();
}

function hoverNeutral() {
    document.querySelector(".bg-left").style.width = "50%";
    document.querySelector(".bg-right").style.width = "50%";
    showNeutral();
}
