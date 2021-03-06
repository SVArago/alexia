function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

$(function () {

    $('.bartender_availability').change(function () {
        var event_id = $(this).data('event-id');

        $.post('/scheduling/ajax/bartender_availability/', {
            event_id: event_id,
            availability_id: $(this).val(),
            csrfmiddlewaretoken: getCookie('csrftoken')
        }, function (data) {
            $('#assigned_bartenders_' + event_id).html(data).effect("highlight");
        }, "text");
    });

    // Bind the event id to the modal and set the existing comment
    $('#comment_modal').on('show.bs.modal', function (event) {
	var modal = $(this);
	var button = $(event.relatedTarget);
	var comment = button.data('comment');
	var event_id = button.data('event-id');
	modal.data('event-id', event_id);
	modal.find('.modal-body input').val(comment);
    });

    // When the modal shows, focus the text input field, so that a user
    // can start typing immediately
    $('#comment_modal').on('shown.bs.modal', function () {
	$(this).find('.modal-body input').focus();
    });

    // Save comment, close modal and update tooltip and modal button data
    $('#comment_modal #save').on('click', function (event) {
	var modal = $(this).parents('#comment_modal');
	var event_id = modal.data('event-id');
	var new_comment = modal.find('.modal-body input').val();
	$.post('/scheduling/ajax/bartender_availability_comment/', {
	    event_id: event_id,
	    comment: new_comment,
	    csrfmiddlewaretoken: getCookie('csrftoken')
	});
	var comment_elem = $('#'+event_id+'.bartender_availability_comment');
	comment_elem.data('comment', new_comment);
	comment_elem.find('span').prop('title', new_comment).tooltip('fixTitle');
	modal.modal('hide');
    });

    $('[data-toggle="tooltip"]').tooltip();

    $('#ical-copy').click(function() {
        $('#ical-url').select();
        document.execCommand('copy');
    });

});
