from ansible_collections.platform.core.plugins.module_utils.application_images import (
    normalize_image, placement_key, selected_image, offline_image, registry_request,
    registry_manifest, registry_config, prepared_image, prepared_lock,
)


class FilterModule:
    def filters(self):
        return dict(application_normalize_image=normalize_image, application_image_key=placement_key,
                    application_selected_image=selected_image, application_offline_image=offline_image,
                    application_registry_request=registry_request, application_registry_manifest=registry_manifest,
                    application_registry_config=registry_config, application_prepared_image=prepared_image,
                    application_prepared_image_lock=prepared_lock)
