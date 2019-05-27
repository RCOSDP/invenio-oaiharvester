$(document).ready(function () {
    const checkTaskStatusEndpoint = '/admin/harvestsettings/status/';
    if ($('#task_id')[0]) {
      trackTaskProgress(checkTaskStatusEndpoint + $('#task_id').text());
    }
});

function trackTaskProgress(loc) {
  $.ajax({
    type: 'GET',
    url: loc,
    success: function(response) {
      console.log('Getting task status...');
      console.log(JSON.stringify(response));
      if(response.state == 'SUCCESS' ||
        response.state == 'FAILURE' ||
        response.state == 'REVOKED') {
        // Change the column values
        $('#task_status').html(response.state);
        $('#task_total').html(response.total_records);
        $('#start_time').html(response.start_time);
        $('#end_time').html(response.end_time);
        $('#pause-btn').addClass('disabled');
        $('#pause-btn').attr('href', '#');
      }
      else {
        $('#task_status').html(response.state);
        setTimeout(function() {
          trackTaskProgress(loc);
        }, 2000);
      }
    },
    error: function(response) {
      $('#task_status').text('ERROR');
      $('#pause-btn').addClass('disabled');
      $('#pause-btn').attr('href', '#');
    }
  });
}
