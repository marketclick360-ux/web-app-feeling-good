// Weekly Meeting Schedule Data - Auto-generated from jw.org
// This file contains midweek meeting info that auto-updates based on current week

const MEETING_SCHEDULE = [
  {
    startDate: "2026-01-05",
    endDate: "2026-01-11",
    weekLabel: "January 5-11, 2026",
    bibleReading: "Isaiah 17-19",
    theme: "Jehovah's Purpose Will Be Fulfilled",
    scripture: "\"Jehovah of armies has sworn: 'Just as I have intended, so it will be, and just as I have decided, that is what will come true.'\"—Isaiah 14:24",
    treasuresTalk: "Jehovah's Purpose Cannot Be Thwarted",
    bibleReadingAssignment: "Isaiah 17:1-14",
    cbsLesson: "lfb lessons 54-55",
    workbookUrl: "https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-January-5-11-2026/"
  },
  {
    startDate: "2026-01-12",
    endDate: "2026-01-18",
    weekLabel: "January 12-18, 2026",
    bibleReading: "Isaiah 20-23",
    theme: "Stay Watchful and Alert",
    scripture: "\"Watchman, what about the night? Watchman, what about the night?\"—Isaiah 21:11",
    treasuresTalk: "Be a Watchman in These Last Days",
    bibleReadingAssignment: "Isaiah 21:1-17",
    cbsLesson: "lfb lessons 55-56",
    workbookUrl: "https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-January-12-18-2026/"
  },
  {
    startDate: "2026-01-19",
    endDate: "2026-01-25",
    weekLabel: "January 19-25, 2026",
    bibleReading: "Isaiah 24-27",
    theme: "Look! This Is Our God!",
    scripture: "\"In that day one will say: 'Look! This is our God! We have hoped in him, and he will save us.'\"—Isaiah 25:9",
    treasuresTalk: "Look! This Is Our God!",
    bibleReadingAssignment: "Isaiah 25:1-9",
    cbsLesson: "lfb lessons 56-57",
    workbookUrl: "https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-January-19-25-2026/"
  },
  {
    startDate: "2026-01-26",
    endDate: "2026-02-01",
    weekLabel: "January 26–February 1, 2026",
    bibleReading: "Isaiah 28-29",
    theme: "Jehovah Will Help His People",
    scripture: "\"Trust in Jehovah forever, for Jah Jehovah is the eternal Rock.\"—Isaiah 26:4",
    treasuresTalk: "Trust in Jehovah Forever",
    bibleReadingAssignment: "Isaiah 28:1-13",
    cbsLesson: "lfb lessons 57-58",
    workbookUrl: "https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-January-26-February-1-2026/"
  },
  {
    startDate: "2026-02-02",
    endDate: "2026-02-08",
    weekLabel: "February 2-8, 2026",
    bibleReading: "Isaiah 30-32",
    theme: "The Result of True Righteousness Will Be Peace",
    scripture: "\"The result of true righteousness will be peace, and the fruitage of true righteousness will be lasting tranquility and security.\"—Isaiah 32:17",
    treasuresTalk: "Find Refuge Under Jehovah's Wings",
    bibleReadingAssignment: "Isaiah 31:1-9",
    cbsLesson: "lfb lessons 58-59",
    workbookUrl: "https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-2-8-2026/"
  },
  {
    startDate: "2026-02-09",
    endDate: "2026-02-15",
    weekLabel: "February 9-15, 2026",
    bibleReading: "Isaiah 33-35",
    theme: "He Is the Stability of Your Times",
    scripture: "\"He is the stability of your times, an abundance of salvation, wisdom, and knowledge.\"—Isaiah 33:6",
    treasuresTalk: "\"He Is the Stability of Your Times\"",
    bibleReadingAssignment: "Isaiah 35:1-10",
    cbsLesson: "lfb lessons 60-61",
    workbookUrl: "https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-9-15-2026/"
  },
  {
    startDate: "2026-02-16",
    endDate: "2026-02-22",
    weekLabel: "February 16-22, 2026",
    bibleReading: "Isaiah 36-37",
    theme: "Jehovah Will Defend His People",
    scripture: "\"I will defend this city and save it for my own sake and for the sake of my servant David.\"—Isaiah 37:35",
    treasuresTalk: "Jehovah Will Defend His People",
    bibleReadingAssignment: "Isaiah 37:1-20",
    cbsLesson: "lfb lessons 61-62",
    workbookUrl: "https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-16-22-2026/"
  },
  {
    startDate: "2026-02-23",
    endDate: "2026-03-01",
    weekLabel: "February 23–March 1, 2026",
    bibleReading: "Isaiah 38-40",
    theme: "Those Hoping in Jehovah Will Regain Power",
    scripture: "\"Those hoping in Jehovah will regain power. They will soar on wings like eagles.\"—Isaiah 40:31",
    treasuresTalk: "Those Hoping in Jehovah Will Regain Power",
    bibleReadingAssignment: "Isaiah 40:21-31",
    cbsLesson: "lfb lessons 62-63",
    workbookUrl: "https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-23-March-1-2026/"
  }
];

// Function to get the current week's schedule
function getCurrentWeekSchedule() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  for (const week of MEETING_SCHEDULE) {
    const start = new Date(week.startDate);
    const end = new Date(week.endDate);
    end.setHours(23, 59, 59, 999);
    
    if (today >= start && today <= end) {
      return week;
    }
  }
  
  // If no matching week found, return the closest upcoming week
  const futureWeeks = MEETING_SCHEDULE.filter(w => new Date(w.startDate) > today);
  if (futureWeeks.length > 0) {
    return futureWeeks[0];
  }
  
  // Fallback to last week in schedule
  return MEETING_SCHEDULE[MEETING_SCHEDULE.length - 1];
}

// Function to render the schedule on the page
function renderCurrentSchedule() {
  const schedule = getCurrentWeekSchedule();
  
  // Update header elements
  const weekInfo = document.querySelector('.week-info');
  if (weekInfo) {
    weekInfo.textContent = 'Week of ' + schedule.weekLabel;
  }
  
  const themeElement = document.querySelector('.meeting-theme');
  if (themeElement) {
    themeElement.innerHTML = 'Midweek Meeting Theme: <strong>\"' + schedule.theme + '\"</strong>';
  }
  
  const scriptureVerse = document.querySelector('.scripture-verse');
  if (scriptureVerse) {
    scriptureVerse.textContent = schedule.scripture;
  }
  
  // Update Bible reading references throughout the page
  const bibleReadingRefs = document.querySelectorAll('[data-bible-reading]');
  bibleReadingRefs.forEach(el => {
    el.textContent = el.textContent.replace(/Isaiah \d+-\d+/g, schedule.bibleReading);
  });
  
  // Update CBS lesson reference
  const cbsRefs = document.querySelectorAll('[data-cbs-lesson]');
  cbsRefs.forEach(el => {
    el.textContent = schedule.cbsLesson;
  });
  
  // Update workbook link
  const workbookLink = document.querySelector('.workbook-link');
  if (workbookLink) {
    workbookLink.href = schedule.workbookUrl;
  }
  
  console.log('Schedule loaded for:', schedule.weekLabel);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', renderCurrentSchedule);
