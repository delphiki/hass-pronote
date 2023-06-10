Example cards
![image](https://github.com/vingerha/hass-pronote/assets/44190435/4e1b8da6-28bd-4aae-a50f-62cd6861e298)
![image](https://github.com/vingerha/hass-pronote/assets/44190435/b6b7f53f-6215-4997-95a3-5b690bf84a21)


```
      - type: markdown
        content: >-
          <table> 

          {% set items =
          state_attr('sensor.pronote_parent_fanny_absences','absences') %}

          {% for i in range(0, items | count, 1) %}

          <tr>

          {%- if items[i].justified == True -%}

          <td> <mark> {{ items[i].from }}</mark></td>

          {% else %}

          <td> <span>{{ items[i].from }}</span></td> 

          {%- endif -%} 

          <td>{{ items[i].hours }}</td>

          <td>{{ items[i].reason }}</td>

          {% endfor %}
        title: Absences
        card_mod:
          style:
            .: |
              ha-card ha-markdown {
                        padding:0px
                        border-top: 1px groove var(--divider-color);
                        overflow-y: scroll;
                        height: 300px;
                      }
              ha-card ha-markdown.no-header {
                padding:0px
              }
            $: |
              h1.card-header {
                background-color:rgb(100, 100, 100);
                  padding: 0px 0px 0px 12px !important;
                  color: white !important;
                  font-weight: normal;
                  font-size: 1.5em !important;
                  border-top-left-radius: 5px; 
                  border-top-right-radius: 5px; 
                  height: 100%;
              }        
            ha-markdown $: |
              h1 {
                  font-weight: normal;
                  font-size: 24px;
              }
              div {
                  background-color:rgb(100, 100, 100);
                  padding: 12px 12px;
                  color:white;
                  font-weight:normal;
                  font-size:1.2em;
                    border-top-left-radius: 5px; 
                    border-top-right-radius: 5px; 
              }
              table{
                border-collapse: collapse;
                font-size: 0.9em;
                font-family: Roboto;
                width: 100%;
                outline: 0px solid #393c3d;
                margin-top: 10px;
              } caption {
                  text-align: center;
                  font-weight: bold;
                  font-size: 1.2em;
              } td {
                  padding: 5px 5px 5px 5px;
                  text-align: left;
                  border-bottom: 0px solid #1c2020;
              }
              tr {
                  border-bottom: 0px solid #1c2020;
              }
              tr:last-of-type {
                  border-bottom: transparent;
              }
              tr:nth-of-type(even) {
                  background-color: rgb(54, 54, 54, 0.3);
              }
              mark {
                  background: lightgreen;
                  border-color: green;
                  border-radius: 10px;
                  padding: 5px;
              }
              span {
                  background: orange;
                  color: #222627;
                  border-radius: 5px;
                  padding: 5px;
              }
              tr:nth-child(n+2) > td:nth-child(2) {
                text-align: left;
              }
      - type: markdown
        content: >-
          <table> 

          {% set items =
          state_attr('sensor.pronote_parent_fanny_timetable_today','lessons') %}
            <tr>
            <td><h4>Start</td>
            <td><h4>End</td>
            <td><h4>Course</td>
            <td><h4>Room</td>
            </tr>
          {% for i in range(0, items | count, 1) %}

          <tr>

          {%- if items[i].canceled != True -%}

          <td> <mark>{{ items[i].time }}</td>

          <td> <mark>{{ items[i].end_at }}</td></mark>

          {% else %}

          <td><del>{{ items[i].time }}</td>

          <td><del>{{ items[i].end_at }}</td>

          {%- endif -%} 

          <td>{{ items[i].lesson }}

          {% if items[i].status != None %}

          <span>{{ items[i].status }}</td> 

          {% endif %}

          <td>{{ items[i].classroom }}</td>

          {% endfor %}
        title: Lesson Today
        card_mod:
          style:
            .: |
              ha-card ha-markdown {
                        padding:0px
                        border-top: 1px groove var(--divider-color);
                        overflow-y: scroll;
                        height: 300px;
                      }
              ha-card ha-markdown.no-header {
                padding:0px
              }
            $: |
              h1.card-header {
                background-color:rgb(100, 100, 100);
                  padding: 0px 0px 0px 12px !important;
                  color: white !important;
                  font-weight: normal;
                  font-size: 1.5em !important;
                  border-top-left-radius: 5px; 
                  border-top-right-radius: 5px; 
                  height: 100%;
              }        
            ha-markdown $: |
              h1 {
                  font-weight: normal;
                  font-size: 24px;
              }
              div {
                  background-color:rgb(100, 100, 100);
                  padding: 12px 12px;
                  color:white;
                  font-weight:normal;
                  font-size:1.2em;
                    border-top-left-radius: 5px; 
                    border-top-right-radius: 5px; 
              }
              table{
                border-collapse: collapse;
                font-size: 0.9em;
                font-family: Roboto;
                width: 100%;
                outline: 0px solid #393c3d;
                margin-top: 10px;
              } caption {
                  text-align: center;
                  font-weight: bold;
                  font-size: 1.2em;
              } td {
                  padding: 5px 5px 5px 5px;
                  text-align: left;
                  border-bottom: 0px solid #1c2020;
              }
              tr {
                  border-bottom: 0px solid #1c2020;
              }
              tr:last-of-type {
                  border-bottom: transparent;
              }
              tr:nth-of-type(even) {
                  background-color: rgb(54, 54, 54, 0.3);
              }
              mark {
                  background: lightgreen;
                  border-color: green;
                  border-radius: 10px;
                  padding: 5px;
              }
              span {
                  background: orange;
                  color: #222627;
                  border-radius: 5px;
                  padding: 5px;
              }
              tr:nth-child(n+2) > td:nth-child(2) {
                text-align: left;
              }
      - type: markdown
        content: >-
          <table> 

          {% set items =
          state_attr('sensor.pronote_parent_fanny_timetable_tomorrow','lessons')
          %}
            <tr>
            <td><h4>Start</td>
            <td><h4>End</td>
            <td><h4>Course</td>
            <td><h4>Room</td>
            </tr>
          {% for i in range(0, items | count, 1) %}

          <tr>

          {%- if items[i].canceled != True -%}

          <td> <mark>{{ items[i].time }}</td>

          <td> <mark>{{ items[i].end_at }}</td></mark>

          {% else %}

          <td><del>{{ items[i].time }}</td>

          <td><del>{{ items[i].end_at }}</td>

          {%- endif -%} 

          <td>{{ items[i].lesson }}

          {% if items[i].status != None %}

          <span>{{ items[i].status }}</td> 

          {% endif %}

          <td>{{ items[i].classroom }}</td>

          {% endfor %}
        title: Lesson Tomorrow
        card_mod:
          style:
            .: |
              ha-card ha-markdown {
                        padding:0px
                        border-top: 1px groove var(--divider-color);
                        overflow-y: scroll;
                        height: 300px;
                      }
              ha-card ha-markdown.no-header {
                padding:0px
              }
            $: |
              h1.card-header {
                background-color:rgb(100, 100, 100);
                  padding: 0px 0px 0px 12px !important;
                  color: white !important;
                  font-weight: normal;
                  font-size: 1.5em !important;
                  border-top-left-radius: 5px; 
                  border-top-right-radius: 5px; 
                  height: 100%;
              }        
            ha-markdown $: |
              h1 {
                  font-weight: normal;
                  font-size: 24px;
              }
              div {
                  background-color:rgb(100, 100, 100);
                  padding: 12px 12px;
                  color:white;
                  font-weight:normal;
                  font-size:1.2em;
                    border-top-left-radius: 5px; 
                    border-top-right-radius: 5px; 
              }
              table{
                border-collapse: collapse;
                font-size: 0.9em;
                font-family: Roboto;
                width: 100%;
                outline: 0px solid #393c3d;
                margin-top: 10px;
              } caption {
                  text-align: center;
                  font-weight: bold;
                  font-size: 1.2em;
              } td {
                  padding: 5px 5px 5px 5px;
                  text-align: left;
                  border-bottom: 0px solid #1c2020;
              }
              tr {
                  border-bottom: 0px solid #1c2020;
              }
              tr:last-of-type {
                  border-bottom: transparent;
              }
              tr:nth-of-type(even) {
                  background-color: rgb(54, 54, 54, 0.3);
              }
              mark {
                  background: lightgreen;
                  border-color: green;
                  border-radius: 10px;
                  padding: 5px;
              }
              span {
                  background: orange;
                  color: #222627;
                  border-radius: 5px;
                  padding: 5px;
              }
              tr:nth-child(n+2) > td:nth-child(2) {
                text-align: left;
              }
      - type: markdown
        content: |2-
            <table>
            {% set items = state_attr('sensor.pronote_parent_fanny_grades','grades')%}
            <tr>
            <td><h4>Date<h3></td>
            <td><h4>Course</td>
            <td><h4>Grade</td>
            <td><h4>Class</td>
            <td><h4>Max</td>
            <td><h4>Min</td>
            <td><h4>Coeff</td>
            </tr>
            {% for i in range(0, items | count, 1) %}
            <tr>    
            <td>{{ items[i].date }}</td>
            <td>{{ items[i].subject }}</td>
            <td>{{ items[i].grade }}/{{ items[i].grade_out_of }}</td>
            <td>{{ items[i].class_average }}</td>
            <td>{{ items[i].max }}</td>
            <td>{{ items[i].min }}</td>
            <td>{{ items[i].coefficient }}</td>
           </tr>
          {% endfor %}
        title: Grades
        card_mod:
          style:
            .: |
              ha-card ha-markdown {
                        padding:0px
                        border-top: 1px groove var(--divider-color);
                        overflow-y: scroll;
                        height: 300px;
                      }
              ha-card ha-markdown.no-header {
                padding:0px
              }
            $: |
              h1.card-header {
                background-color:rgb(100, 100, 100);
                  padding: 0px 0px 0px 12px !important;
                  color: white !important;
                  font-weight: normal;
                  font-size: 1.5em !important;
                  border-top-left-radius: 5px; 
                  border-top-right-radius: 5px; 
                  height: 100%;
              }        
            ha-markdown $: |
              h1 {
                  font-weight: normal;
                  font-size: 24px;
              }
              div {
                  background-color:rgb(100, 100, 100);
                  padding: 12px 12px;
                  color:white;
                  font-weight:normal;
                  font-size:1.2em;
                    border-top-left-radius: 5px; 
                    border-top-right-radius: 5px; 
              }
              table{
                border-collapse: collapse;
                font-size: 0.9em;
                font-family: Roboto;
                width: 100%;
                outline: 0px solid #393c3d;
                margin-top: 10px;
              } caption {
                  text-align: center;
                  font-weight: bold;
                  font-size: 1.2em;
              } td {
                  padding: 5px 5px 5px 5px;
                  text-align: left;
                  border-bottom: 0px solid #1c2020;
              }
              tr {
                  border-bottom: 0px solid #1c2020;
              }
              tr:last-of-type {
                  border-bottom: transparent;
              }
              tr:nth-of-type(even) {
                  background-color: rgb(54, 54, 54, 0.3);
              }
              mark {
                  background: lightgreen;
                  border-color: green;
                  border-radius: 10px;
                  padding: 5px;
              }
              span {
                  background: orange;
                  color: #222627;
                  border-radius: 5px;
                  padding: 5px;
              }
              tr:nth-child(n+2) > td:nth-child(2) {
                text-align: left;
              }
      - type: markdown
        content: >-
          <table> 

          {% set items =
          state_attr('sensor.pronote_parent_fanny_timetable_next_day','lessons')
          %}
            <tr>
            <td><h4>Start</td>
            <td><h4>End</td>
            <td><h4>Course</td>
            <td><h4>Room</td>
            </tr>
          {% for i in range(0, items | count, 1) %}

          <tr>

          {%- if items[i].canceled != True -%}

          <td> <mark>{{ items[i].time }}</td>

          <td> <mark>{{ items[i].end_at }}</td></mark>

          {% else %}

          <td><del>{{ items[i].time }}</td>

          <td><del>{{ items[i].end_at }}</td>

          {%- endif -%} 

          <td>{{ items[i].lesson }}

          {% if items[i].status != None %}

          <span>{{ items[i].status }}</td> 

          {% endif %}

          <td>{{ items[i].classroom }}</td>

          {% endfor %}
        title: Lesson Next Day
        card_mod:
          style:
            .: |
              ha-card ha-markdown {
                        padding:0px
                        border-top: 1px groove var(--divider-color);
                        overflow-y: scroll;
                        height: 300px;
                      }
              ha-card ha-markdown.no-header {
                padding:0px
              }
            $: |
              h1.card-header {
                background-color:rgb(100, 100, 100);
                  padding: 0px 0px 0px 12px !important;
                  color: white !important;
                  font-weight: normal;
                  font-size: 1.5em !important;
                  border-top-left-radius: 5px; 
                  border-top-right-radius: 5px; 
                  height: 100%;
              }        
            ha-markdown $: |
              h1 {
                  font-weight: normal;
                  font-size: 24px;
              }
              div {
                  background-color:rgb(100, 100, 100);
                  padding: 12px 12px;
                  color:white;
                  font-weight:normal;
                  font-size:1.2em;
                    border-top-left-radius: 5px; 
                    border-top-right-radius: 5px; 
              }
              table{
                border-collapse: collapse;
                font-size: 0.9em;
                font-family: Roboto;
                width: 100%;
                outline: 0px solid #393c3d;
                margin-top: 10px;
              } caption {
                  text-align: center;
                  font-weight: bold;
                  font-size: 1.2em;
              } td {
                  padding: 5px 5px 5px 5px;
                  text-align: left;
                  border-bottom: 0px solid #1c2020;
              }
              tr {
                  border-bottom: 0px solid #1c2020;
              }
              tr:last-of-type {
                  border-bottom: transparent;
              }
              tr:nth-of-type(even) {
                  background-color: rgb(54, 54, 54, 0.3);
              }
              mark {
                  background: lightgreen;
                  border-color: green;
                  border-radius: 10px;
                  padding: 5px;
              }
              span {
                  background: orange;
                  color: #222627;
                  border-radius: 5px;
                  padding: 5px;
              }
              tr:nth-child(n+2) > td:nth-child(2) {
                text-align: left;
              }
      - type: markdown
        content: >
          <table>

          {% set items =
          state_attr('sensor.pronote_parent_fanny_evaluations','evaluations')%}

          {% for i in range(0, items | count, 1) %}

          <tr><td>{{ items[i].subject }}</td>

          {% set acquisitions = items[i].acquisitions %}

          {% for j in range(0,acquisitions|count,1) %}

          <tr>

          <td>{{ acquisitions[j].name }}</td>

          <td>{{ acquisitions[j].domain }}</td>

          <td width="8%">

          {% if acquisitions[j].level == 'Très bonne maîtrise' %} 🟢+

          {% elif acquisitions[j].level == 'Maîtrise satisfaisante' %} 🟢

          {% elif acquisitions[j].level == "Début de maîtrise" %} 🟡

          {% elif acquisitions[j].level == 'Maîtrise fragile'  %} 🟠

          {% elif acquisitions[j].level == 'Presque maîtrisé'  %} 🟡 {% else %}
          ? 

          {% endif %}</td>

          </tr>

          {% endfor %}

          </tr>

          {% endfor %}
        title: Evaluations
        card_mod:
          style:
            .: |
              ha-card ha-markdown {
                        padding:0px
                        border-top: 1px groove var(--divider-color);
                        overflow-y: scroll;
                        height: 300px;
                      }
              ha-card ha-markdown.no-header {
                padding:0px
              }
            $: |
              h1.card-header {
                background-color:rgb(100, 100, 100);
                  padding: 0px 0px 0px 12px !important;
                  color: white !important;
                  font-weight: normal;
                  font-size: 1.5em !important;
                  border-top-left-radius: 5px; 
                  border-top-right-radius: 5px; 
                  height: 100%;
              }        
            ha-markdown $: |
              h1 {
                  font-weight: normal;
                  font-size: 24px;
              }
              div {
                  background-color:rgb(100, 100, 100);
                  padding: 12px 12px;
                  color:white;
                  font-weight:normal;
                  font-size:1.2em;
                    border-top-left-radius: 5px; 
                    border-top-right-radius: 5px; 
              }
              table{
                border-collapse: collapse;
                font-size: 0.9em;
                font-family: Roboto;
                width: 100%;
                outline: 0px solid #393c3d;
                margin-top: 10px;
              } caption {
                  text-align: center;
                  font-weight: bold;
                  font-size: 1.2em;
              } td {
                  padding: 5px 5px 5px 5px;
                  text-align: left;
                  border-bottom: 0px solid #1c2020;
              }
              tr {
                  border-bottom: 0px solid #1c2020;
              }
              tr:last-of-type {
                  border-bottom: transparent;
              }
              tr:nth-of-type(even) {
                  background-color: rgb(54, 54, 54, 0.3);
              }
              mark {
                  background: lightgreen;
                  border-color: green;
                  border-radius: 10px;
                  padding: 5px;
              }
              span {
                  background: orange;
                  color: #222627;
                  border-radius: 5px;
                  padding: 5px;
              }
              tr:nth-child(n+2) > td:nth-child(2) {
                text-align: left;
              }
