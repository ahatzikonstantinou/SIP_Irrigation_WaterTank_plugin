$(document).ready(function() {
  //
  // get all water tank info for initial setup

  function template(water_tank, state="" )
  {
    // console.log(`Will generate tr for id: ${water_tank.id}, label: ${water_tank.label}, percentage: ${water_tank.percentage}, sensor_error: ${water_tank.invalid_sensor_measurement}, last_updated: ${water_tank.last_updated}, state: "${state}"`);
    let str_percentage = "";
    let width_percentage = 0;
    let last_updated = water_tank.last_updated;
    if(last_updated == null)
    {
      last_updated = "";
    }
    if(water_tank.invalid_sensor_measurement)
    {
      state = "sensor_error";
    }
    else if(water_tank.percentage != null)
    {
      let percentage = Math.round(water_tank.percentage);
      str_percentage = percentage + "%";
      width_percentage = percentage;
    }
    let hidden = !water_tank.enabled ? "hidden" : "";
    // console.log(`Water_tank_id:${water_tank.id}, enabled: ${water_tank.enabled}, hidden:${hidden}`);

    return `<tr id="${water_tank.id}" ${hidden}>
      <td style="white-space: nowrap;">
        <div class="water-tank-label">${water_tank.label}</div>
        <div class="last_updated">${last_updated}</div></td>
      <td style="width:100%">
        <div style="width: 100%;
        height: 2em;
        background-color: lightcyan;
        border-radius: 10px;
        border:1px solid cyan;
        text-align: center;
        vertical-align: middle;
        position: relative;">
          <div class="percent-bar ${state}" style="width: ${width_percentage}%;
          height: 100%;
          position: absolute;
          z-index: 2;">
          </div>
          <div class="status-bar-text" style="width: 100%;
          height: 100%;
          z-index: 3;
          position: absolute;">
          <h4 class="${state}" style="display:inline;text-align: center;
          line-height:2em;" class="${state}">${str_percentage}</h4>
        </div>
      </td>
    </tr>`;
  }


  // Create a new div element
  var many_water_tank_div = $(`<p style="padding-top:1em;">Water Tanks</p><div id="water_tank_container">
    <table id="water_tank_table" style="width:100%;border: 1px solid #2E3959;border-radius: 12px;padding: 4px;">        
    </table>
  </div>`);

  var single_water_tank_div = $(`<div id="water_tank_container" style="padding-top:1em;">
    <table id="water_tank_table" style="width:100%;padding: 4px;">        
    </table>
  </div>`);

  // add water tank display only to home page
  let url_parts = window.location.href.split('/');
  if(url_parts[url_parts.length-1].length == 0)
  {
    $.getJSON('water-tank-get-all', function(data){
      
      // Add the new div right after the "options" div
      if(data.length > 1)
      {        
        $('#options').after(many_water_tank_div);
      }
      else
      {      
        $('#options').after(single_water_tank_div);
      }

      $.each( data, function( i, water_tank ) {
        let tr = template( water_tank, DetermineWaterTankState(water_tank) );
        $('#water_tank_table').append(tr);

      });  
    });
  }

  //
  // Register mqtt client to update water tank data based on incoming mqtt messages
  // Create a client instance
  $.getJSON('water-tank-get_mqtt_settings', function(data)
  {
    let mqtt_settings = null;
  
    console.log('mqtt_settings: ', data);
    mqtt_settings = data;

    const client_id = "browser_" + uuidv4();
    console.log('water_tank.js connecting to mqtt broker with ' +
      mqtt_settings.broker_host + ", " + mqtt_settings.mqtt_broker_ws_port + ", " + client_id);
    client = new Paho.MQTT.Client(mqtt_settings.broker_host, mqtt_settings.mqtt_broker_ws_port, client_id);

    // set callback handlers
    client.onConnectionLost = onConnectionLost;
    client.onMessageArrived = onMessageArrived;

    // connect the client
    client.connect({onSuccess:onConnect});

    // called when the client connects
    function onConnect() {
      // Once a connection has been made, make a subscription and send a message.
      console.log("onConnect");
      client.subscribe(mqtt_settings.data_publish_mqtt_topic);
    }

    // called when the client loses its connection
    function onConnectionLost(responseObject) {
      if (responseObject.errorCode !== 0) {
        console.log("onConnectionLost:"+responseObject.errorMessage);
      }
    }

    // called when a message arrives
    function onMessageArrived(message) {
      // console.log("onMessageArrived:"+message.payloadString);
      try
      {
        const water_tanks = JSON.parse(message.payloadString);
        Object.keys(water_tanks).forEach(e => {
            // console.log(`key= $${e} value=$${water_tanks[e]}`);
            const id = e;
            const water_tank = water_tanks[e];
            // console.log('id: ' + id + ", water_tank: ", water_tank);
            
            if(water_tank.invalid_sensor_measurement)
            {
              $(`#${water_tank.id}`).replaceWith( template( water_tank ) );
            }
            else if(water_tank.percentage != null)
            {
              let state = "normal";              

              if(water_tank.critical_level != null &&
                water_tank.percentage <= water_tank.critical_level)
              {
                state = "critical";
              }
              else if(water_tank.warning_level != null &&
                water_tank.percentage <= water_tank.warning_level)
              {
                state = "warning";
              }
              else if(water_tank.overflow_level != null &&
                water_tank.percentage >= water_tank.overflow_level)
              {
                state = "overflow";
              }              
              $(`#${water_tank.id}`).replaceWith( template( water_tank, DetermineWaterTankState(water_tank) ) );
            }
            
        });        
      }
      catch(e)
      {
        console.error(e);
      }
    }
  });

});

function DetermineWaterTankState(water_tank)
{
  let state = "normal";

  if(water_tank.invalid_sensor_measurement)
  {
    state = "sensor_error";
  }
  else if(water_tank.percentage != null)
  {                  
   if(water_tank.critical_level != null &&
      water_tank.percentage <= water_tank.critical_level)
    {
      state = "critical";
    }
    else if(water_tank.warning_level != null &&
      water_tank.percentage <= water_tank.warning_level)
    {
      state = "warning";
    }
    else if(water_tank.overflow_level != null &&
      water_tank.percentage >= water_tank.overflow_level)
    {
      state = "overflow";
    }
  }

  return state;
}

function uuidv4() {
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
  );
}