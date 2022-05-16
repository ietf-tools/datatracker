/* Add the moment object to the global scope - needed until inline scripts using
 * Moment.js are eliminated. When that happens, can import moment in the js files
 * that need it. */
import moment from "moment-timezone/builds/moment-timezone-with-data-10-year-range";
window.moment = moment;
