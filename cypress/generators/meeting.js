import { DateTime } from 'luxon'
import { faker } from '@faker-js/faker'

export default {
  generateAgendaResponse ({ future = false }) {
    const startDate = future ? DateTime.fromISO(faker.date.future(1).toISOString()) : DateTime.fromISO(faker.date.past(5, DateTime.utc().minus({ months: 3 })).toISOString())
    const endDate = startDate.plus({ days: 7 })

    return {
      meeting: {
        number: '123',
        city: faker.address.cityName(),
        startDate: startDate.toISODate(),
        endDate: endDate.toISODate(),
        updated: faker.date.between(startDate.toISO(), endDate.toISO()).toISOString(),
        timezone: faker.address.timeZone(),
        infoNote: faker.lorem.paragraph(4),
        warningNote: ''
      },
      categories: [],
      isCurrentMeeting: future,
      useHedgeDoc: true,
      schedule: [],
      floors: []
    }
  }
}
