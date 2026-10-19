package qa.sdku;

import tnt.evoscada.api.Evo;

/** QA-only user script: no tag lookups, subscriptions or data mutations. */
public final class StartupMock {
    public static void main(Evo evo) {
        System.out.println("SDKU_EVO_MOCK_STARTED");
    }
}
