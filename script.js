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
