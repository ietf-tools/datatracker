import Highcharts from "highcharts";

import Highcharts_Exporting from "highcharts/modules/exporting";
import Highcharts_Offline_Exporting from "highcharts/modules/offline-exporting";
import Highcharts_Export_Data from "highcharts/modules/export-data";
import Highcharts_Accessibility from"highcharts/modules/accessibility";

Highcharts_Exporting(Highcharts);
Highcharts_Offline_Exporting(Highcharts);
Highcharts_Export_Data(Highcharts);
Highcharts_Accessibility(Highcharts);

window.Highcharts = Highcharts;
