from gig_backend.router import route_request


def test_enabled_cloud_auto_routes_complex_text_only():
    args = dict(requested='auto', text='Research this deeply', operation='identify',
                local_available=True, cloud_available=True, allow_cloud_auto=True)
    assert route_request(**args, has_image=False).model == 'kimi'
    assert route_request(**args, has_image=True).model == 'local'


def test_auto_never_sends_data_to_cloud_without_selection():
    result = route_request(requested='auto', text='Research this deeply', has_image=False,
                           operation='identify', local_available=True, cloud_available=True)
    assert result.model == 'local'
    assert 'never' in result.reason


def test_router_suggests_but_does_not_execute_action():
    result = route_request(requested='auto', text='Upload to Drive', has_image=False,
                           operation='identify', local_available=True, cloud_available=True)
    assert result.model == 'local'
    assert result.suggested_workflow == 'approval_required'


def test_router_uses_local_vision_for_scan():
    result = route_request(requested='auto', text='Transcribe this page', has_image=True,
                           operation='scan', local_available=True, cloud_available=True)
    assert result.model == 'local'
    assert result.suggested_workflow == 'review_then_save'
