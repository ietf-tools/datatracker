import { Calendar } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import iCalendarPlugin from '@fullcalendar/icalendar';
import bootstrap5Plugin from '@fullcalendar/bootstrap5';

global.FullCalendar = Calendar;
global.dayGridPlugin = dayGridPlugin;
global.iCalendarPlugin = iCalendarPlugin;
global.bootstrap5Plugin = bootstrap5Plugin;
