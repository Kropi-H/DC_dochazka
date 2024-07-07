$(function () {
    $('#datetimepicker1').datetimepicker({format: "DD-MM-YYYY"});
});
$(function () {
    $('#datetimepicker2').datetimepicker({format: "DD-MM-YYYY"});
});

function clearInfoCount(){
    $.get(`/clear_info_count`)
}

setTimeout(function() {
  document.getElementById("alert_info").style.display = "none";
}, 6000);

function printPage() {
  // Vytvoření nového elementu <link> pro načtení Bootstrap CSS
  var printCss = document.createElement('link');
  printCss.rel = 'stylesheet';
  printCss.media = 'print';
  printCss.type = "text/css";
  printCss.href = '/static/print.css';


  // Přidání elementu <link> do hlavičky (<head>) stránky
  document.head.appendChild(printCss);

  // Počkejme chvíli na načtení CSS a potom spustíme tisk
  setTimeout(function() {
      window.print(); // Spuštění tisku
  }, 1000); // Počkejte 1 sekundu (1000 ms) na načtení CSS
}
