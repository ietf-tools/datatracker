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
        timezone: 'Asia/Tokyo',
        infoNote: faker.lorem.paragraph(4),
        warningNote: ''
      },
      categories: [
        [],
        [],
        [
          {
            "label": "Plenary",
            "keyword": "plenary",
            "toggled_by": [],
            "is_bof": false,
            "children": [
              {
                "label": "IETF Plenary",
                "keyword": "ietf-plenary",
                "toggled_by": [
                  "plenary",
                  "ietf"
                ],
                "is_bof": false
              }
            ]
          },
        ]
      ],
      isCurrentMeeting: future,
      useHedgeDoc: true,
      schedule: [],
      floors: []
    }
  }
}
