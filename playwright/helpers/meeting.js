const { DateTime } = require('luxon')
const { faker } = require('@faker-js/faker')
const seedrandom = require('seedrandom')
const _ = require('lodash')
const slugify = require('slugify')
const ms = require('ms')

const floorsMeta = require('../data/meeting-floors')

const urlRe = /http[s]?:\/\/(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+/
const conferenceDomains = ['webex.com', 'zoom.us', 'jitsi.org', 'meetecho.com', 'gather.town']

const xslugify = (str) => slugify(str.replace('/', '-'), { lower: true, strict: true })

const TEST_SEED = 123
const sessionsWithNotes = [3, 6, 20, 48, 49, 60]
const sessionsCancelled = [29, 93]
const sessionsRescheduled = [76]
const sessionsMissingAgenda = [5, 10]
const sessionsWithWebex = [3, 4]

// Use constant randomness seed
seedrandom(TEST_SEED.toString(), { global: true })
faker.seed(TEST_SEED)
const { random, sample, sampleSize } = _.runInContext()

/**
 * Generate area response from label + children
 */
function createArea ({ label, children = [] }) {
  return {
    label,
    keyword: xslugify(label),
    toggled_by: [],
    is_bof: false,
    children: children.map(gr => {
      gr.toggled_by.push(xslugify(label))
      return gr
    })
  }
}

/**
 * Generate group response from label
 */
const uniqueGroupNames = []
function createGroup ({ label, mayBeBof = false, toggledBy = [] }) {
  // make sure group name is unique
  while (!label) {
    const nameAttempt = faker.word.verb()
    if (!uniqueGroupNames.includes(nameAttempt)) {
      label = nameAttempt
      uniqueGroupNames.push(nameAttempt)
    }
  }

  // Set toggledBy
  if (!toggledBy) {
    toggledBy = []
  }

  // 10% chance of BoF, if enabled
  const isBof = mayBeBof && random(0, 100) < 10
  if (isBof) {
    toggledBy.push('bof')
  }

  return {
    label,
    keyword: xslugify(label),
    toggled_by: toggledBy,
    is_bof: isBof
  }
}

/**
 * Find area and group based on group slug
 */
function findAreaGroup (slug, areas) {
  for (const area of areas) {
    for (const group of area.children) {
      if (group.keyword === slug) {
        return { area, group }
      }
    }
  }
  throw new Error('Requested group does not exist!')
}

/**
 * Reverse areas and groups mapping
 */
function reverseAreaGroupsMapping (areas) {
  const groups = []
  for (const area of areas) {
    for (const group of area.children) {
      groups.push({
        ...group,
        area
      })
    }
  }
  return groups
}

function getEventStatus (idx) {
  if (sessionsCancelled.includes(idx)) {
    return 'canceled'
  } else if (sessionsRescheduled.includes(idx)) {
    return 'resched'
  } else {
    return 'sched'
  }
}

/**
 * Generate event
 */
let lastEventId = 100000
let lastSessionId = 25000
let lastRecordingId = 150000
function createEvent ({
  name = '',
  slotName = '',
  startDateTime,
  duration = '1h',
  area,
  group,
  type = 'other',
  status = 'sched',
  hasLocation = true,
  hasNote = false,
  hasAgenda = false,
  showAgenda = false,
  hasRecordings = false,
  hasVideoStream = true,
  hasWebex = false,
  isBoF = false
}, floors) {
  const floor = sample(floors)
  const room = hasLocation ? sample(floor.rooms) : { name: 'Somewhere' }
  const eventName = name ?? faker.lorem.sentence(random(2, 5))
  return {
    id: ++lastEventId,
    sessionId: ++lastSessionId,
    room: room.name,
    location: hasLocation
      ? {
          short: floor.short,
          name: floor.name
        }
      : {},
    acronym: group.keyword,
    duration: typeof duration === 'string' ? ms(duration) / 1000 : duration,
    name: eventName,
    slotName: slotName,
    startDateTime: startDateTime.toISO({ includeOffset: false, suppressMilliseconds: true }),
    status,
    type,
    isBoF,
    filterKeywords: [
      'coding',
      'hackathon',
      'hackathon-sessc'
    ],
    groupAcronym: group.keyword,
    groupName: faker.lorem.sentence(random(2, 5)),
    groupParent: {
      acronym: area.keyword
    },
    note: (hasNote || status === 'resched') ? faker.lorem.sentence(4) : '',
    remoteInstructions: '',
    flags: {
      agenda: hasAgenda,
      showAgenda
    },
    agenda: {
      url: hasAgenda ? 'https://datatracker.ietf.org/meeting/123/materials/agenda-123-ietf-sessa-00' : null
    },
    orderInMeeting: 1,
    short: eventName,
    sessionToken: 'sessa',
    links: {
      chat: `https://zulip.ietf.org/#narrow/stream/${group.keyword}`,
      chatArchive: `https://zulip.ietf.org/#narrow/stream/${group.keyword}`,
      recordings: hasRecordings
        ? [
            {
              id: ++lastRecordingId,
              name: `recording-123-${group.keyword}-1`,
              title: `Video recording for ${group.keyword} on ${startDateTime.toFormat('yyyy-LL-dd \'at\' HH:mm:ss')}`,
              url: 'https://www.youtube.com/watch?v=1eq_5xvacl0'
            }
          ]
        : [],
      videoStream: showAgenda && hasVideoStream ? 'https://meetings.conf.meetecho.com/ietf{meeting.number}/?group={group.acronym}&short={short}&item={order_number}' : null,
      audioStream: hasAgenda ? 'https://mp3.conf.meetecho.com/ietf123/{group.acronym}/{order_number}.m3u' : null,
      webex: hasWebex ? 'https://webex.com/123' : null,
      onsiteTool: hasAgenda ? 'https://meetings.conf.meetecho.com/onsite{meeting.number}/?group={group.acronym}&short={short}&item={order_number}' : null,
      calendar: `/meeting/123/session/${lastSessionId}.ics`
    }
  }
}

module.exports = {
  /**
   * Generate a standard agenda data reponse
   */
  generateAgendaResponse ({ dateMode = 'past', skipSchedule = false } = {}) {
    // Get random date but always start on a saturday
    let startDate = null
    switch (dateMode) {
      case 'current': {
        startDate = DateTime.fromISO('2022-02-01T13:45:15', { zone: 'Asia/Tokyo' }).startOf('week').minus({ days: 2 })
        break
      }
      case 'future': {
        startDate = DateTime.fromISO(faker.date.future({ years: 1 }).toISOString(), { zone: 'Asia/Tokyo' }).startOf('week').minus({ days: 2 })
        break
      }
      default: {
        startDate = DateTime.fromISO(faker.date.past({ years: 5, refDate: DateTime.utc().minus({ months: 3 }) }).toISOString(), { zone: 'Asia/Tokyo' }).startOf('week').minus({ days: 2 })
        break
      }
    }
    const endDate = startDate.plus({ days: 7 })

    // Generate floors
    const floors = _.times(6, (idx) => {
      const floorIdx = idx + 1
      const floor = floorsMeta[idx]
      return {
        id: floorIdx,
        image: `/media/floor/${floor.path}`,
        name: `Level ${_.startCase(faker.color.human())} ${floorIdx}`,
        short: `L${floorIdx}`,
        width: floor.width,
        height: floor.height,
        rooms: _.times(random(5, 10), (ridx) => {
          const roomName = `${faker.science.chemicalElement().name} ${floorIdx}-${ridx + 1}`
          // Keep 10% margin on each side
          const roomXUnit = Math.round(floor.width / 10)
          const roomYUnit = Math.round(floor.height / 10)
          const roomX = random(roomXUnit, roomXUnit * 8)
          const roomY = random(roomYUnit, roomYUnit * 8)
          return {
            id: floorIdx * 100 + ridx,
            name: roomName,
            functionalName: _.startCase(faker.lorem.words(2)),
            slug: xslugify(roomName),
            left: roomX,
            right: roomX + roomXUnit,
            top: roomY,
            bottom: roomY + roomYUnit
          }
        })
      }
    })

    // Generate categories (groups/areas)

    const categories = []

    if (!skipSchedule) {
      // Generate first group of areas
      // -----------------------------
      const firstAreas = []
      const firstAreasNames = ['ABC', 'DEF', 'GHI', 'JKL', 'MNO', 'PQR', 'STU']
      for (const area of firstAreasNames) {
        firstAreas.push(createArea({
          label: area,
          children: _.times(random(2, 25), (idx) => {
            return createGroup({ mayBeBof: true })
          })
        }))
      }
      categories.push(firstAreas)

      // Generate second group of areas
      // ------------------------------
      const secondAreas = []
      for (const area of ['UVW', 'XYZ0']) {
        secondAreas.push(createArea({
          label: area,
          children: _.times(random(2, 25), (idx) => {
            return createGroup({ mayBeBof: true })
          })
        }))
      }
      categories.push(secondAreas)

      // Generate last group of areas
      // ----------------------------
      categories.push(
        [
          createArea({
            label: 'Administrative',
            children: [
              createGroup({ label: 'IETF Registration' })
            ]
          }),
          createArea({
            label: 'Coding',
            children: [
              createGroup({ label: 'Hackathon', toggledBy: ['hackathon'] }),
              createGroup({ label: 'Code Sprint', toggledBy: ['tools'] })
            ]
          }),
          createArea({
            label: 'Office hours',
            children: firstAreasNames.map(n => createGroup({ label: `${n} Office Hours` }))
          }),
          createArea({
            label: 'Open meeting',
            children: [
              createGroup({ label: 'WG Chairs Forum' }),
              createGroup({ label: 'Newcomers\' Feedback Session' })
            ]
          }),
          createArea({
            label: 'Plenary',
            children: [
              createGroup({ label: 'IETF Plenary', toggledBy: ['ietf'] })
            ]
          }),
          createArea({
            label: 'Presentation',
            children: [
              createGroup({ label: 'Hackathon Kickoff', toggledBy: ['hackathon'] }),
              createGroup({ label: 'Hackathon Project Results Presentations', toggledBy: ['hackathon'] }),
              createGroup({ label: 'Host Speaker Series', toggledBy: ['ietf'] })
            ]
          }),
          createArea({
            label: 'Social',
            children: [
              createGroup({ label: 'Newcomers\' Quick Connections' }),
              createGroup({ label: 'Welcome Reception', toggledBy: ['ietf'] }),
              createGroup({ label: 'Break', toggledBy: ['secretariat'] }),
              createGroup({ label: 'Beverage and Snack Break', toggledBy: ['secretariat'] }),
              createGroup({ label: 'Hackdemo Happy Hour', toggledBy: ['hackathon'] })
            ]
          }),
          createArea({
            label: 'Tutorial',
            children: [
              createGroup({ label: 'Tutorial: Newcomers\' Overview' })
            ]
          }),
          createArea({
            label: '',
            children: [
              createGroup({ label: 'BoF' }),
              createGroup({ label: 'qwerty', toggledBy: ['abc'] }),
              createGroup({ label: 'azerty', toggledBy: ['def'] }),
              createGroup({ label: 'Tools' })
            ]
          })
        ]
      )
    }

    // Generate schedule

    const schedule = []

    if (!skipSchedule) {
      let sessionIdx = 0
      const daySessions = []
      const regGroups = reverseAreaGroupsMapping([...categories[0], ...categories[1]])

      // DAY 1 - No regular sessions
      // ---------------------------
      const day1 = startDate

      schedule.push(createEvent({
        name: 'Hackathon',
        startDateTime: day1.set({ hour: 9, minute: 30 }),
        duration: '11.5h',
        ...findAreaGroup('hackathon', categories[2]),
        showAgenda: true,
        hasAgenda: true,
        hasRecordings: true,
        hasVideoStream: false
      }, floors))

      schedule.push(createEvent({
        name: 'Code Sprint',
        startDateTime: day1.set({ hour: 10 }),
        duration: '12h',
        ...findAreaGroup('code-sprint', categories[2])
      }, floors))

      schedule.push(createEvent({
        name: 'Hackathon Kickoff',
        startDateTime: day1.set({ hour: 10, minute: 30 }),
        duration: '30m',
        ...findAreaGroup('hackathon-kickoff', categories[2]),
        showAgenda: true,
        hasAgenda: true,
        hasRecordings: true,
        hasVideoStream: false
      }, floors))

      // DAY 2 - No regular sessions
      // ---------------------------
      const day2 = startDate.plus({ days: 1 })

      schedule.push(createEvent({
        name: 'Hackathon',
        startDateTime: day2.set({ hour: 9, minute: 30 }),
        duration: '6.5h',
        ...findAreaGroup('hackathon', categories[2]),
        showAgenda: true,
        hasAgenda: true,
        hasVideoStream: false
      }, floors))

      schedule.push(createEvent({
        name: 'IETF Registration',
        startDateTime: day2.set({ hour: 10 }),
        duration: '8h',
        ...findAreaGroup('ietf-registration', categories[2])
      }, floors))

      schedule.push(createEvent({
        name: 'Tutorial: Newcomers',
        startDateTime: day2.set({ hour: 12, minute: 30 }),
        duration: '1h',
        ...findAreaGroup('tutorial-newcomers-overview', categories[2]),
        showAgenda: true,
        hasRecordings: true,
        hasVideoStream: true
      }, floors))

      schedule.push(createEvent({
        name: 'Hackathon Results Presentations',
        startDateTime: day2.set({ hour: 14 }),
        duration: '2h',
        ...findAreaGroup('hackathon-project-results-presentations', categories[2])
      }, floors))

      schedule.push(createEvent({
        name: 'Newcomers\' Quick Connections (Note that pre-registration is required)',
        startDateTime: day2.set({ hour: 16 }),
        duration: '1h',
        ...findAreaGroup('newcomers-quick-connections', categories[2]),
        hasLocation: false
      }, floors))

      schedule.push(createEvent({
        name: 'ABC AD Office Hours',
        startDateTime: day2.set({ hour: 16 }),
        duration: '1h',
        ...findAreaGroup('abc-office-hours', categories[2])
      }, floors))

      schedule.push(createEvent({
        name: 'DEF AD Office Hours',
        startDateTime: day2.set({ hour: 16, minute: 15 }),
        duration: '45m',
        ...findAreaGroup('def-office-hours', categories[2])
      }, floors))

      schedule.push(createEvent({
        name: 'Welcome Reception',
        startDateTime: day2.set({ hour: 17 }),
        duration: '2h',
        ...findAreaGroup('welcome-reception', categories[2])
      }, floors))

      // DAY 3-7 - Regular Sessions
      // --------------------------
      for (let dayIdx = 2; dayIdx < 7; dayIdx++) {
        const curDay = startDate.plus({ days: dayIdx })
        daySessions.push(...sampleSize(regGroups, 24))

        schedule.push(createEvent({
          name: 'Continental Breakfast',
          startDateTime: curDay.set({ hour: 8, minute: 30 }),
          duration: '1.5h',
          type: 'break',
          ...findAreaGroup('beverage-and-snack-break', categories[2])
        }, floors))

        schedule.push(createEvent({
          name: 'ABC AD Office Hours',
          startDateTime: curDay.set({ hour: 8, minute: 30 }),
          duration: '8.5h',
          ...findAreaGroup('abc-office-hours', categories[2])
        }, floors))

        schedule.push(createEvent({
          name: 'IETF Registration',
          startDateTime: curDay.set({ hour: 8, minute: 30 }),
          duration: '8h',
          ...findAreaGroup('ietf-registration', categories[2])
        }, floors))

        schedule.push(createEvent({
          name: 'DEF AD Office Hours',
          startDateTime: curDay.set({ hour: 9 }),
          duration: '8.5h',
          ...findAreaGroup('def-office-hours', categories[2])
        }, floors))

        schedule.push(createEvent({
          name: 'GHI AD Office Hours',
          startDateTime: curDay.set({ hour: 9 }),
          duration: '30m',
          ...findAreaGroup('ghi-office-hours', categories[2]),
          hasLocation: false
        }, floors))

        // -> Session I
        _.times(8, () => { // 8 lanes per session time
          const { area, ...group } = daySessions.pop()
          schedule.push(createEvent({
            slotName: 'Session I',
            startDateTime: curDay.set({ hour: 10 }),
            duration: '2h',
            type: 'regular',
            group,
            area,
            status: getEventStatus(sessionIdx),
            hasNote: sessionsWithNotes.includes(sessionIdx),
            isBoF: group.is_bof,
            showAgenda: true,
            hasAgenda: !sessionsMissingAgenda.includes(sessionIdx),
            hasRecordings: !sessionsMissingAgenda.includes(sessionIdx),
            hasWebex: sessionsWithWebex.includes(sessionIdx)
          }, floors))
          sessionIdx++
        })

        schedule.push(createEvent({
          name: 'Break',
          startDateTime: curDay.set({ hour: 12 }),
          duration: '1.5h',
          type: 'break',
          ...findAreaGroup('beverage-and-snack-break', categories[2])
        }, floors))

        // -> Session II
        _.times(8, () => { // 8 lanes per session time
          const { area, ...group } = daySessions.pop()
          schedule.push(createEvent({
            slotName: 'Session II',
            startDateTime: curDay.set({ hour: 13, minute: 30 }),
            duration: '1h',
            type: 'regular',
            group,
            area,
            status: getEventStatus(sessionIdx),
            hasNote: sessionsWithNotes.includes(sessionIdx),
            isBoF: group.is_bof,
            showAgenda: true,
            hasAgenda: !sessionsMissingAgenda.includes(sessionIdx),
            hasRecordings: !sessionsMissingAgenda.includes(sessionIdx),
            hasWebex: sessionsWithWebex.includes(sessionIdx)
          }, floors))
          sessionIdx++
        })

        // -> No 3rd session on last day
        if (dayIdx < 6) {
          schedule.push(createEvent({
            name: 'Beverage and Snack Break',
            startDateTime: curDay.set({ hour: 14, minute: 30 }),
            duration: '30m',
            type: 'break',
            ...findAreaGroup('beverage-and-snack-break', categories[2])
          }, floors))

          // -> Session III
          _.times(8, () => { // 8 lanes per session time
            const { area, ...group } = daySessions.pop()
            schedule.push(createEvent({
              slotName: 'Session III',
              startDateTime: curDay.set({ hour: 15 }),
              duration: '2h',
              type: 'regular',
              group,
              area,
              status: getEventStatus(sessionIdx),
              hasNote: sessionsWithNotes.includes(sessionIdx),
              isBoF: group.is_bof,
              showAgenda: true,
              hasAgenda: !sessionsMissingAgenda.includes(sessionIdx),
              hasRecordings: !sessionsMissingAgenda.includes(sessionIdx),
              hasWebex: sessionsWithWebex.includes(sessionIdx)
            }, floors))
            sessionIdx++
          })
        }

        // -> Plenary
        if (dayIdx === 4) {
          schedule.push(createEvent({
            name: 'Beverage and Snack Break',
            startDateTime: curDay.set({ hour: 17 }),
            duration: '30m',
            type: 'break',
            ...findAreaGroup('beverage-and-snack-break', categories[2])
          }, floors))

          schedule.push(createEvent({
            name: 'IETF Plenary',
            startDateTime: curDay.set({ hour: 17, minute: 30 }),
            duration: '2h',
            type: 'plenary',
            ...findAreaGroup('ietf-plenary', categories[2])
          }, floors))
        }
      }
    }

    // Return response object

    return {
      meeting: {
        number: '123',
        city: faker.location.city(),
        startDate: startDate.toISODate(),
        endDate: endDate.toISODate(),
        updated: faker.date.between({ from: startDate.toISO(), to: endDate.toISO() }).toISOString(),
        timezone: 'Asia/Tokyo',
        infoNote: faker.lorem.paragraph(4),
        warningNote: ''
      },
      categories,
      isCurrentMeeting: dateMode !== 'past',
      usesNotes: true,
      schedule,
      floors
    }
  },

  /**
   * Format URL by replacing inline variables
   *
   * @param {String} url Raw URL
   * @param {Object} session Session Object
   * @param {String} meetingNumber Meeting Number
   * @returns Formatted URL
   */
  formatLinkUrl: (url, session, meetingNumber) => {
    return url
      ? url.replace('{meeting.number}', meetingNumber)
        .replace('{group.acronym}', session.groupAcronym)
        .replace('{short}', session.short)
        .replace('{order_number}', session.orderInMeeting)
      : url
  },

  /**
   * Find the first URL in text matching a conference domain
   *
   * @param {String} txt Raw Text
   * @returns First URL found
   */
  findFirstConferenceUrl: (txt) => {
    try {
      const fUrl = txt.match(urlRe)
      if (fUrl && fUrl[0].length > 0) {
        const pUrl = new URL(fUrl[0])
        if (conferenceDomains.some(d => pUrl.hostname.endsWith(d))) {
          return fUrl[0]
        }
      }
    } catch (err) { }
    return null
  }
}
