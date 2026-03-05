"""Standard objects, action descriptors, and endpoint paths."""

ENDPOINT_PATHS = [
    "/s/sfsites/aura",
    "/sfsites/aura",
    "/aura",
    "/s/aura",
]

# Action descriptors
DESCRIPTORS = {
    "getObjectInfo": "aura://RecordUiController/ACTION$getObjectInfo",
    "getItems": (
        "serviceComponent://ui.force.components.controllers.lists."
        "selectableListDataProvider.SelectableListDataProviderController"
        "/ACTION$getItems"
    ),
    "getConfigData": (
        "serviceComponent://ui.force.components.controllers.hostConfig."
        "HostConfigController/ACTION$getConfigData"
    ),
    "getListsByObjectName": "aura://ListUiController/ACTION$getListsByObjectName",
    "getProfileMenuResponse": (
        "serviceComponent://ui.communities.components.aura.components.forceCommunity."
        "profileMenu.ProfileMenuController/ACTION$getProfileMenuResponse"
    ),
    "createRecord": (
        "serviceComponent://ui.force.components.controllers.recordGlobalValueProvider."
        "RecordGvpController/ACTION$createRecord"
    ),
    "updateRecord": (
        "serviceComponent://ui.force.components.controllers.recordGlobalValueProvider."
        "RecordGvpController/ACTION$updateRecord"
    ),
    "deleteRecord": (
        "serviceComponent://ui.force.components.controllers.recordGlobalValueProvider."
        "RecordGvpController/ACTION$deleteRecord"
    ),
}

STANDARD_OBJECTS = [
    "Account",
    "Asset",
    "Campaign",
    "CampaignMember",
    "Case",
    "CaseComment",
    "CollaborationGroup",
    "Contact",
    "ContentDocument",
    "ContentVersion",
    "ContentWorkspace",
    "Contract",
    "Dashboard",
    "Document",
    "EmailMessage",
    "EmailTemplate",
    "Event",
    "FeedItem",
    "Idea",
    "Individual",
    "Knowledge__kav",
    "Lead",
    "LiveChatTranscript",
    "Note",
    "Opportunity",
    "OpportunityLineItem",
    "Order",
    "OrderItem",
    "Organization",
    "PermissionSet",
    "PermissionSetAssignment",
    "Pricebook2",
    "PricebookEntry",
    "Product2",
    "Profile",
    "Report",
    "ServiceResource",
    "Site",
    "SocialPost",
    "Solution",
    "Task",
    "Topic",
    "User",
    "UserRole",
    "WorkOrder",
    "WorkOrderLineItem",
]

# Common Apex controllers found in communities
COMMON_APEX_CONTROLLERS = [
    "LightningLoginFormController.login",
    "LightningForgotPasswordController.forgotPassword",
    "LightningSelfRegisterController.selfRegister",
    "LightningSelfRegisterController.getExtraFields",
    "LightningSelfRegisterController.setExperienceId",
    "LightningLoginFormController.setExperienceId",
    "CommunitiesLandingController.forwardToCustomAuthPage",
    "SiteRegisterController.registerUser",
]
