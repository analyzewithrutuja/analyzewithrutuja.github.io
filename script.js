function showBusiness() {
    document.getElementById("imgNeutral").classList.remove("active");
    document.getElementById("imgEngineer").classList.remove("active");
    document.getElementById("imgBusiness").classList.add("active");
}

function showEngineer() {
    document.getElementById("imgNeutral").classList.remove("active");
    document.getElementById("imgBusiness").classList.remove("active");
    document.getElementById("imgEngineer").classList.add("active");
}

function showNeutral() {
    document.getElementById("imgBusiness").classList.remove("active");
    document.getElementById("imgEngineer").classList.remove("active");
    document.getElementById("imgNeutral").classList.add("active");
}
